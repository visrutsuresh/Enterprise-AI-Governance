import csv
import io
import os
import threading
import uuid

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from app import audit, precedent, ratelimit, store, sweep
from app.agents import approval_workflow_agent, executive_advisory_agent
from app.graph import graph, initial_state
from app.state import RISK_TIERS
from app.schemas import UserCreate, UserUpdate
from app.users import (
    User,
    UserManager,
    auth_backend,
    create_user_table,
    current_user,
    fastapi_users,
    require_admin,
    require_reviewer,
    session_maker,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()  # tables exist when the API BOOTS, not when this module imports, so tests can drive it without a database
    # a pack swap is a governance decision; it must not silently revert on reboot
    for key, value in store.all_settings().items():
        if key in ("POLICY_PACK", "FRAMEWORK_PACK"):
            os.environ[key] = value
    await create_user_table()
    try:
        precedent.ensure_collection()  # label the Weaviate drawer on a fresh machine
    except Exception as e:
        print(f"[precedent] ensure_collection failed (Weaviate down?): {e}", flush=True)
    yield  # everything before the yield is startup; nothing to tear down after


app = FastAPI(title="Enterprise AI Governance API", lifespan=lifespan)

# comma-separated list, e.g. "https://governance.vercel.app,http://localhost:3000"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _login_rate_limit(request: Request, call_next):
    # no public registration here, but the login door still gets a per-IP lock
    if request.method == "POST" and request.url.path == "/auth/login":
        try:
            ratelimit.check(f"login:{ratelimit.client_ip(request)}", 10, 300)
        except HTTPException as e:
            return JSONResponse({"detail": e.detail}, status_code=e.status_code)
    return await call_next(request)


app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth", tags=["auth"])
# no register router on purpose: accounts exist only when an admin creates them (see the /users routes).
# the ONE exception is the first-run bootstrap below, or a fresh install would have
# no admin and therefore no way to create the first account.


@app.get("/auth/needs-setup")
async def needs_setup():
    # the login page asks this to decide whether to show the one-time setup form
    async with session_maker() as session:
        n = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    return {"needs_setup": n == 0}


class BootstrapIn(BaseModel):
    # EmailStr, not str: UserCreate validates the address further down, and a plain
    # str would let that ValidationError escape the handler as a 500. The founding
    # admin mistyping their own address is the likeliest error on this screen, and
    # it must read as "that is not a valid address", not "Internal Server Error".
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


@app.post("/auth/bootstrap")
async def bootstrap_admin(payload: BootstrapIn):
    # first-run only: creates the founding admin while the system has ZERO
    # accounts, then this door closes forever. Single worker makes the
    # count-then-create window a non-issue in practice.
    async with session_maker() as session:
        n = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        if n:
            raise HTTPException(status_code=403, detail="setup is already complete; ask an administrator for an account")
        db = SQLAlchemyUserDatabase(session, User)
        mgr = UserManager(db)
        try:
            created = await mgr.create(UserCreate(email=payload.email, password=payload.password, role="admin"))
        except UserAlreadyExists:
            raise HTTPException(status_code=409, detail="that email is already registered")
        created = await db.update(created, {"role": "admin"})
        return {"id": str(created.id), "email": created.email, "role": created.role}


@app.get("/")
def health():
    return {"status": "ok", "product": "governance"}


@app.get("/health")
def health_alias():
    # the Phase 0 boot check hits this
    return {"status": "ok", "product": "governance"}


@app.get("/healthz")
def healthz():
    # the honest health check: touches each dependency instead of just answering.
    # / and /health stay instant for uptime pings; this one is for humans and deploy
    # gates. Named to match the sibling ticket system so all three answer the same way.
    out = {"api": "ok"}
    # up/down only, no exception text: this route is unauthenticated and driver
    # errors would leak host and user strings to anyone who asks
    try:
        with store._connect() as conn:
            conn.execute("SELECT 1")
        out["postgres"] = "ok"
    except Exception:
        out["postgres"] = "down"
    try:
        precedent._client().close()
        out["weaviate"] = "ok"
    except Exception:
        out["weaviate"] = "down"
    out["status"] = "ok" if out["postgres"] == "ok" and out["weaviate"] == "ok" else "degraded"
    return out


@app.get("/config")
def brand_config():
    return {
        "brand_name": os.getenv("BRAND_NAME", "Governance"),
        "brand_tagline": os.getenv("BRAND_TAGLINE", ""),
    }


# --- assets ------------------------------------------------------------------

PIPELINE_TIMEOUT_S = 1500  # 25 min wall clock; the per-node guards in graph.py (1200s + one retry) do the real capping
TERMINAL_STATUSES = ("assessed", "error")


class RegisterIn(BaseModel):
    description: str


def _invoke_guarded(asset_id: str, initial: dict):
    # ONE attempt: every node already retries once inside guarded(), so an outer
    # retry would re-run the whole assessment and double the Modal bill
    print(f"[pipeline] {asset_id} start", flush=True)
    box = {}

    def work():
        try:
            box["final"] = graph.invoke(initial, {"recursion_limit": 40})
        except Exception as e:
            box["error"] = str(e)

    th = threading.Thread(target=work, daemon=True)  # daemon: a hung run is abandoned, never blocks shutdown
    th.start()
    th.join(PIPELINE_TIMEOUT_S)
    if "final" in box:
        print(f"[pipeline] {asset_id} done", flush=True)
        return box["final"]
    print(f"[pipeline] {asset_id} failed: {box.get('error', 'timeout')}", flush=True)
    return None


def _process(asset_id: str, description: str):
    initial = initial_state(asset_id, description)
    final = _invoke_guarded(asset_id, initial)
    if final is None:
        # a dead run must SAY it died, never strand at "processing" (the #1 lesson)
        initial["status"] = "error"
        initial["error"] = "The assessment crashed or timed out before finishing. Nothing was saved half-done: register the asset again."
        store.save(initial)
        return
    if final.get("status") not in TERMINAL_STATUSES:
        final["status"] = "error"
        final["error"] = final.get("error") or "The assessment ended without a verdict. Register the asset again."
    store.save(final)


@app.post("/assets")
def register_asset(payload: RegisterIn, background: BackgroundTasks, user: User = Depends(require_reviewer)):
    ratelimit.check(f"assets:{user.email}", 10, 86_400)  # each registration runs the paid inspector pipeline
    if not payload.description.strip():
        raise HTTPException(status_code=400, detail="describe the AI system to register")
    asset_id = f"AI-{uuid.uuid4().hex[:8]}"
    store.save_pending(asset_id, payload.description.strip()[:80], "pipeline", datetime.now(timezone.utc))
    background.add_task(_process, asset_id, payload.description.strip())
    return {"asset_id": asset_id, "status": "processing"}


@app.get("/assets")
def list_assets(user: User = Depends(require_reviewer)):
    return store.list_all()


@app.get("/assets/{asset_id}")
def get_asset(asset_id: str, user: User = Depends(require_reviewer)):
    state = store.get(asset_id)
    if state is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return state


@app.get("/assets/{asset_id}/audit")
def get_audit(asset_id: str, user: User = Depends(require_reviewer)):
    # the tamper-evident trail: verify() re-walks the hash chain and reports
    # the FIRST entry whose hash no longer follows from the one before it,
    # which is what an edit straight into the JSONB blob looks like
    state = store.get(asset_id)
    if state is None:
        raise HTTPException(status_code=404, detail="asset not found")
    log = state.get("audit") or []
    broken_at = audit.verify(log)
    return {
        "asset_id": asset_id,
        "entries": log,
        "count": len(log),
        "intact": broken_at == -1,
        "broken_at": None if broken_at == -1 else broken_at,
    }


# --- packs: the NFR-1 swap surface ------------------------------------------


class PackSwapIn(BaseModel):
    policy_pack: str | None = None
    framework_pack: str | None = None


@app.get("/packs")
def active_packs(user: User = Depends(require_reviewer)):
    from app import packs as _packs
    p, f = _packs.load_policy_pack(), _packs.load_framework_pack()
    return {"policy_pack": {"id": p["pack_id"], "name": p.get("name", ""), "rules": len(p["rules"])},
            "framework_pack": {"id": f["pack_id"], "name": f.get("name", ""), "tiers": len(f["tiers"])}}


@app.post("/packs/activate")
def activate_packs(payload: PackSwapIn, user: User = Depends(require_admin)):
    # the stage moment: change the env var, nothing else, then re-score.
    # Loaders read the env at call time, so every later model call and the
    # deterministic re-score below see the new pack with zero code change.
    from app import packs as _packs
    for env_var, name, kind in (("POLICY_PACK", payload.policy_pack, "policy_packs"),
                                ("FRAMEWORK_PACK", payload.framework_pack, "framework_packs")):
        if name:
            if not (_packs.DATA_DIR / kind / f"{name}.json").exists():
                raise HTTPException(status_code=404, detail=f"no pack named {name!r} in {kind}")
            os.environ[env_var] = name
            store.set_setting(env_var, name)  # survives a restart; read back in lifespan
    rescore = sweep.rescore_policy()
    return {"active": active_packs(user), "rescore": rescore}


# --- the other three clocks: nightly sweep + on-demand (D41) ----------------


class SweepIn(BaseModel):
    limit: int = 10


# up to 10 serial model calls per run can take many minutes; running that inside
# the HTTP request froze the tower for the whole duration. The run now happens in
# the background and the tower polls /sweep/status. In-process state is correct
# here for the same reason as the rate limiter: the app is pinned to one worker.
_SWEEP_STATE: dict = {"state": "idle"}
_SWEEP_LOCK = threading.Lock()  # sync endpoints run on a threadpool; check-and-set must be atomic


def _sweep_worker(limit: int) -> None:
    try:
        report = sweep.run_sweep(limit)
        _SWEEP_STATE.update(state="done", report=report, error=None)
    except Exception as e:
        _SWEEP_STATE.update(state="error", report=None, error=str(e))


@app.post("/sweep/run")
def run_sweep(background: BackgroundTasks, payload: SweepIn | None = None, user: User = Depends(require_admin)):
    limit = payload.limit if payload else 10
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit must be 1-200")
    with _SWEEP_LOCK:
        if _SWEEP_STATE["state"] == "running":
            raise HTTPException(status_code=409, detail="a sweep is already running")
        ratelimit.check("sweep:global", 2, 3600)  # after the 409 guard, so a refused call never burns a slot
        _SWEEP_STATE.update(state="running", report=None, error=None, started_at=datetime.now(timezone.utc).isoformat())
    background.add_task(_sweep_worker, limit)
    return {"state": "started", "limit": limit}


@app.get("/sweep/status")
def sweep_status(user: User = Depends(require_reviewer)):
    return _SWEEP_STATE


def _find_finding(finding_id: str):
    # finding ids look like f-AI-0042-pol-1: the asset id is the middle piece
    core = finding_id.removeprefix("f-")
    asset_id = core.rsplit("-", 2)[0] if core.count("-") >= 2 else core
    state = store.get(asset_id)
    if state is None:
        return None, None, None
    assessment = (state.get("asset", {}).get("assessment") or {})
    for f in assessment.get("findings", []):
        if f.get("finding_id") == finding_id:
            return state, assessment, f
    return state, assessment, None


@app.post("/flags/{finding_id}/route")
def route_flag(finding_id: str, user: User = Depends(require_reviewer)):
    state, assessment, finding = _find_finding(finding_id)
    if state is None:
        raise HTTPException(status_code=404, detail="no asset for that finding id")
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found on its asset")
    routing = approval_workflow_agent(finding, state["asset_id"])
    finding["routed_to"] = routing["team"]
    state["audit"] = audit.chain_as(state.get("audit") or [],
                                    [f"approval_workflow: {finding_id} routed to {routing['team']} ({routing['why']})"],
                                    by=user.email)
    store.save(state)
    return {"finding_id": finding_id, **routing}


# --- exports: the artifact you hand an external auditor ----------------------


def _no_formula(v):
    # these files get opened in Excel by auditors; a cell starting =, +, - or @
    # would execute as a formula, and names/reasons/model text are attacker-writable
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
        return "'" + v
    return v


def _csv_response(filename: str, header: list, rows: list) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows([[_no_formula(c) for c in row] for row in rows])
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/export/register.csv")
def export_register(user: User = Depends(require_reviewer)):
    rows = store.list_all()
    return _csv_response(
        "register.csv",
        ["asset_id", "name", "type", "owner", "lifecycle", "status", "risk_tier", "risk_level", "source", "created_at", "open_findings"],
        [[r.get("asset_id"), r.get("name"), r.get("type"), r.get("owner"), r.get("lifecycle"), r.get("status"),
          r.get("risk_tier"), r.get("risk_level"), r.get("source"), r.get("created_at"), r.get("open_findings")] for r in rows],
    )


@app.get("/export/findings.csv")
def export_findings(user: User = Depends(require_reviewer)):
    rows = store.list_findings()
    out = []
    for r in rows:
        f = r.get("finding") or {}
        review = f.get("review") or {}
        out.append([
            f.get("finding_id"), r.get("asset_id"), r.get("asset_name"), r.get("risk_tier"),
            f.get("inspector"), f.get("control_id"), f.get("severity"), f.get("status"),
            f.get("plain"), f.get("remediation"),
            review.get("verdict"), review.get("by"), review.get("at"), review.get("reason"),
        ])
    return _csv_response(
        "findings.csv",
        ["finding_id", "asset_id", "asset_name", "risk_tier", "inspector", "control_id", "severity", "status",
         "finding", "remediation", "review_verdict", "review_by", "review_at", "review_reason"],
        out,
    )


@app.get("/assets/{asset_id}/audit.csv")
def export_audit(asset_id: str, user: User = Depends(require_reviewer)):
    state = store.get(asset_id)
    if state is None:
        raise HTTPException(status_code=404, detail="no such asset")
    log = state.get("audit") or []
    broken_at = audit.verify(log)
    return _csv_response(
        f"audit-{asset_id}.csv",
        ["entry", "step", "at", "by", "prev_hash", "hash", "intact"],
        [[i, e.get("step"), e.get("ts"), e.get("by"), e.get("prev"), e.get("hash"), broken_at == -1 or i < broken_at]
         for i, e in enumerate(log)],
    )


class TierOverrideIn(BaseModel):
    tier: str
    reason: str


@app.post("/assets/{asset_id}/tier")
def override_tier(asset_id: str, payload: TierOverrideIn, user: User = Depends(require_reviewer)):
    # the model mis-tiers roughly 1 in 4 assets; governance means a human can
    # correct it, and the correction itself goes on the tamper-evident record
    tier = payload.tier.strip().lower()
    if tier not in RISK_TIERS:
        raise HTTPException(status_code=422, detail=f"tier must be one of: {', '.join(RISK_TIERS)}")
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="a tier override needs a reason: say why the assigned tier is wrong")
    state = store.get(asset_id)
    if state is None:
        raise HTTPException(status_code=404, detail="no such asset")
    # same fallback the asset page uses, so the recorded "from" matches what the screen showed
    assessment_tier = (state.get("asset", {}).get("assessment") or {}).get("risk_tier") or ""
    old = (state.get("risk_tier") or assessment_tier or "").lower() or "unassigned"
    if old == tier:
        raise HTTPException(status_code=409, detail=f"asset is already tier {tier}")
    state["risk_tier"] = tier
    state["tier_override"] = {  # latest override, in full, for the asset page
        "from": old,
        "to": tier,
        "reason": reason,
        "by": user.email,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    state["audit"] = audit.chain_as(
        state.get("audit") or [],
        [f"tier_override: {asset_id} {old} -> {tier} by {user.email} ({reason})"],
        by=user.email,
    )
    store.save(state)
    return {"asset_id": asset_id, "from": old, "to": tier, "by": user.email}


FLAG_VERDICTS = ("approved", "overridden")


class FlagDecisionIn(BaseModel):
    verdict: str  # approved = the finding is real | overridden = dismissed, and why
    reason: str = ""


@app.post("/flags/{finding_id}/decision")
def decide_flag(finding_id: str, payload: FlagDecisionIn, user: User = Depends(require_reviewer)):
    # Routing says who should look. This says what they CONCLUDED, which is the half
    # an auditor actually asks about: not "was it flagged" but "who dismissed it, and why".
    if payload.verdict not in FLAG_VERDICTS:
        raise HTTPException(status_code=422, detail="verdict must be approved or overridden")
    reason = payload.reason.strip()
    if payload.verdict == "overridden" and not reason:
        raise HTTPException(status_code=422, detail="an override needs a reason: say why this finding does not apply")
    state, _assessment, finding = _find_finding(finding_id)
    if state is None:
        raise HTTPException(status_code=404, detail="no asset for that finding id")
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found on its asset")
    if finding.get("review"):
        raise HTTPException(status_code=409, detail="this flag has already been decided")
    owner = (finding.get("owner") or "").lower()
    if owner and owner in (user.email.lower(), user.email.lower().split("@")[0]):
        # maker-checker: whoever owns the remediation work cannot also sign it off.
        # matches both full-email and short-name owner conventions
        raise HTTPException(status_code=403, detail="you own this finding's remediation; a different reviewer must decide it")

    finding["review"] = {
        "verdict": payload.verdict,
        "reason": reason,
        "by": user.email,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    # an override closes the finding; an approval CONFIRMS it, so the remediation work stays open
    if payload.verdict == "overridden":
        finding["status"] = "dismissed"
    state["audit"] = audit.chain_as(
        state.get("audit") or [],
        [f"reviewer_decision: {finding_id} {payload.verdict} by {user.email} ({reason or 'confirmed as raised'})"],
        by=user.email,
    )
    store.save(state)
    return {
        "finding_id": finding_id,
        "verdict": payload.verdict,
        "status": finding["status"],
        "reason": reason,
        "by": user.email,
    }


# --- remediation: the half of governance that is somebody's actual job -------
#
# Routing says who should look. A decision says what they concluded. Neither says
# whether the work got DONE, which is what an auditor asks next. These two routes
# add the missing middle: an owner, a deadline, and a state that moves.

REMEDIATION_STATUSES = ("open", "in_progress", "awaiting_evidence", "closed", "dismissed")
# dismissed is deliberately NOT a board column: dismissing a finding is an
# override, which requires a written reason, and that path stays on /decision.
BOARD_STATUSES = ("open", "in_progress", "awaiting_evidence", "closed")


def _finding_view(row: dict) -> dict:
    # one flat row for the board: the finding plus the asset context it needs
    f = row["finding"]
    return {
        "finding_id": f.get("finding_id"),
        "asset_id": row["asset_id"],
        "asset_name": row["asset_name"],
        "risk_tier": row["risk_tier"],
        "inspector": f.get("inspector"),
        "control_id": f.get("control_id"),
        "severity": f.get("severity"),
        "plain": f.get("plain"),
        "remediation": f.get("remediation"),
        "status": (f.get("status") or "open").lower(),
        "owner": f.get("owner"),
        "due_at": f.get("due_at"),
        "routed_to": f.get("routed_to"),
        "evidence_files": f.get("evidence_files") or [],
        "review": f.get("review"),
    }


def _is_overdue(view: dict, today: date) -> bool:
    if not view["due_at"] or view["status"] in ("closed", "dismissed"):
        return False
    try:
        return date.fromisoformat(str(view["due_at"])[:10]) < today
    except ValueError:
        return False  # an unparseable date is a data problem, not an overdue item


@app.get("/remediation")
def remediation_queue(
    mine: bool = False,
    unassigned: bool = False,
    overdue: bool = False,
    team: str = "",
    status: str = "",
    user: User = Depends(require_reviewer),
):
    # The board reads this. Filters are applied here rather than in SQL because the
    # whole estate is ~200 findings: readable beats clever at this size.
    if status and status not in REMEDIATION_STATUSES:
        raise HTTPException(status_code=422,
                            detail=f"status must be one of: {', '.join(REMEDIATION_STATUSES)}")
    today = datetime.now(timezone.utc).date()
    rows = []
    for raw in store.list_findings():
        v = _finding_view(raw)
        if not v["finding_id"]:
            continue  # a malformed finding cannot be worked on; fan_in already logs these
        if status and v["status"] != status:
            continue
        if mine and (v["owner"] or "").lower() != user.email.lower():
            continue
        if unassigned and v["owner"]:
            continue
        if team and (v["routed_to"] or "") != team:
            continue
        if overdue and not _is_overdue(v, today):
            continue
        v["overdue"] = _is_overdue(v, today)
        rows.append(v)
    counts = {s: 0 for s in REMEDIATION_STATUSES}
    for v in rows:
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    return {
        "findings": rows,
        "counts": counts,
        "overdue": sum(1 for v in rows if v["overdue"]),
        "unassigned": sum(1 for v in rows if not v["owner"]),
    }


class FlagPatchIn(BaseModel):
    owner: str | None = None  # null clears it back to unassigned
    due_at: str | None = None  # ISO date, null clears it
    status: str | None = None


@app.patch("/flags/{finding_id}")
def update_flag(finding_id: str, payload: FlagPatchIn, user: User = Depends(require_reviewer)):
    sent = payload.model_fields_set  # so "clear the owner" is distinguishable from "leave it alone"
    if not sent:
        raise HTTPException(status_code=422, detail="send at least one of owner, due_at, status")

    new_status = None
    if "status" in sent:
        new_status = (payload.status or "").lower()
        if new_status not in BOARD_STATUSES:
            # naming the board columns, not all five words, is the useful error here
            raise HTTPException(
                status_code=422,
                detail=f"status must be one of: {', '.join(BOARD_STATUSES)}. "
                       "To dismiss a finding use the override verdict, which requires a reason.")

    if "due_at" in sent and payload.due_at:
        try:
            date.fromisoformat(payload.due_at[:10])
        except ValueError:
            raise HTTPException(status_code=422, detail="due_at must be a date like 2026-07-31")

    state, _assessment, finding = _find_finding(finding_id)
    if state is None:
        raise HTTPException(status_code=404, detail="no asset for that finding id")
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found on its asset")
    if (finding.get("status") or "open").lower() == "dismissed":
        # a dismissal is a recorded judgement with a reason attached. Quietly
        # reviving it by dragging a card would undermine the whole audit story.
        raise HTTPException(status_code=409,
                            detail="this finding was dismissed by an override; it cannot be moved")

    notes = []
    if "owner" in sent:
        owner = (payload.owner or "").strip() or None
        finding["owner"] = owner
        notes.append(f"owner set to {owner}" if owner else "owner cleared")
    if "due_at" in sent:
        due = (payload.due_at or "").strip() or None
        finding["due_at"] = due
        notes.append(f"due {due}" if due else "due date cleared")
    if new_status is not None:
        was = (finding.get("status") or "open").lower()
        finding["status"] = new_status
        notes.append(f"status {was} -> {new_status}")

    # the product's promise: remediation state cannot change without a trace
    state["audit"] = audit.chain_as(
        state.get("audit") or [],
        [f"remediation: {finding_id} {'; '.join(notes)} by {user.email}"],
        by=user.email,
    )
    store.save(state)
    return _finding_view({
        "asset_id": state["asset_id"],
        "asset_name": state.get("asset", {}).get("name"),
        "risk_tier": state.get("asset", {}).get("risk_tier"),
        "risk_level": None,
        "finding": finding,
    })


# --- evidence: the proof that the remediation actually happened -------------
#
# The board already has an AWAITING EVIDENCE column, which until now was a
# promise with nothing behind it. A closed finding that an auditor cannot
# inspect is a claim, not a control. These three routes are the difference.

MAX_EVIDENCE_BYTES = 10 * 1024 * 1024  # 10MB: screenshots and signed PDFs, not datasets
ALLOWED_EVIDENCE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "application/pdf",
    "text/plain",
    "text/csv",
}


@app.post("/flags/{finding_id}/evidence")
async def upload_evidence(
    finding_id: str,
    file: UploadFile = File(...),
    user: User = Depends(require_reviewer),
):
    if file.content_type not in ALLOWED_EVIDENCE_TYPES:
        raise HTTPException(status_code=400, detail=f"unsupported type: {file.content_type}")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > MAX_EVIDENCE_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 10 MB)")

    state, _assessment, finding = _find_finding(finding_id)
    if state is None:
        raise HTTPException(status_code=404, detail="no asset for that finding id")
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found on its asset")
    if (finding.get("status") or "open").lower() == "dismissed":
        # same reasoning as the PATCH route: a dismissal is a recorded judgement,
        # and attaching proof of work to it would tell a confusing story
        raise HTTPException(status_code=409, detail="this finding was dismissed by an override; it takes no evidence")

    row = store.add_evidence(
        finding_id, state["asset_id"], file.filename, file.content_type, data, user.email
    )
    # mirror the metadata onto the finding so the board can show a count without
    # a second query per card. The TABLE stays the source of truth for content.
    finding["evidence_files"] = (finding.get("evidence_files") or []) + [
        {
            "id": row["id"],
            "filename": row["filename"],
            "size": row["size"],
            "uploaded_by": row["uploaded_by"],
            "at": row["created_at"].isoformat() if row["created_at"] else None,
        }
    ]
    state["audit"] = audit.chain_as(
        state.get("audit") or [],
        [f"evidence: {finding_id} +{file.filename} ({len(data)} bytes) by {user.email}"],
        by=user.email,
    )
    store.save(state)
    return {
        "id": row["id"],
        "finding_id": finding_id,
        "filename": row["filename"],
        "size": row["size"],
        "uploaded_by": row["uploaded_by"],
    }


@app.get("/flags/{finding_id}/evidence")
def list_flag_evidence(finding_id: str, user: User = Depends(require_reviewer)):
    return store.list_evidence(finding_id)


@app.get("/evidence/{evidence_id}")
def download_evidence(evidence_id: int, user: User = Depends(require_reviewer)):
    row = store.get_evidence(evidence_id)
    if row is None:
        raise HTTPException(status_code=404, detail="evidence not found")
    return Response(
        content=bytes(row["data"]),
        media_type=row["content_type"] or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{row["filename"]}"'},
    )


@app.get("/brief")
def executive_brief(user: User = Depends(require_reviewer)):
    stats = sweep._estate_stats()
    brief = executive_advisory_agent(f"Estate scorecard: {stats}")
    return {"brief": brief, "estate": stats}


@app.get("/users/me")
def who_am_i(user: User = Depends(current_user)):
    return {"id": str(user.id), "email": user.email, "role": user.role, "is_active": user.is_active}


ROLES = ("reviewer", "admin")


@app.get("/users")
async def list_users(user: User = Depends(require_admin)):
    async with session_maker() as session:
        rows = (await session.execute(select(User).order_by(User.email))).scalars().all()
        return [{"id": str(x.id), "email": x.email, "role": x.role, "is_active": x.is_active} for x in rows]


@app.post("/users")
async def create_account(payload: UserCreate, user: User = Depends(require_admin)):
    if payload.role not in ROLES:
        raise HTTPException(status_code=422, detail="role must be reviewer or admin")
    async with session_maker() as session:
        db = SQLAlchemyUserDatabase(session, User)
        mgr = UserManager(db)
        try:
            created = await mgr.create(payload)
        except UserAlreadyExists:
            raise HTTPException(status_code=409, detail="an account with that email already exists")
        created = await db.update(created, {"role": payload.role})  # pin the role even if a schema tweak ever drops it from create
        return {"id": str(created.id), "email": created.email, "role": created.role, "is_active": created.is_active}


@app.patch("/users/{user_id}")
async def edit_account(user_id: uuid.UUID, payload: UserUpdate, user: User = Depends(require_admin)):
    role = getattr(payload, "role", None)
    if role is not None and role not in ROLES:
        raise HTTPException(status_code=422, detail="role must be reviewer or admin")
    async with session_maker() as session:
        db = SQLAlchemyUserDatabase(session, User)
        mgr = UserManager(db)
        target = await db.get(user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="user not found")
        try:
            updated = await mgr.update(payload, target, safe=False)
        except UserAlreadyExists:
            raise HTTPException(status_code=409, detail="an account with that email already exists")
        return {"id": str(updated.id), "email": updated.email, "role": updated.role, "is_active": updated.is_active}


@app.delete("/users/{user_id}")
async def deactivate_account(user_id: uuid.UUID, user: User = Depends(require_admin)):
    # deactivate, never hard-delete: the audit trail keeps pointing at a real account
    async with session_maker() as session:
        db = SQLAlchemyUserDatabase(session, User)
        target = await db.get(user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="user not found")
        if target.id == user.id:
            raise HTTPException(status_code=400, detail="you cannot deactivate your own account")
        await db.update(target, {"is_active": False})
        return {"id": str(target.id), "deactivated": True}


@app.get("/metrics")
def executive_metrics(user: User = Depends(require_reviewer)):
    # the executive dashboard: the five PDF metric categories. Every real number
    # is computed from the estate in sweep._estate_metrics; sample-labelled ones
    # carry {"sample": true} so the UI badges them instead of implying measurement.
    return sweep._estate_metrics()
