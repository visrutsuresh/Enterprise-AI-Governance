import os
import threading
import uuid

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from pydantic import BaseModel
from sqlalchemy import select

from app import audit, precedent, store, sweep
from app.agents import approval_workflow_agent, executive_advisory_agent
from app.graph import graph, initial_state
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
    await create_user_table()
    try:
        precedent.ensure_collection()  # label the Weaviate drawer on a fresh machine
    except Exception as e:
        print(f"[precedent] ensure_collection failed (Weaviate down?): {e}", flush=True)
    yield  # everything before the yield is startup; nothing to tear down after


app = FastAPI(title="Enterprise AI Governance API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth", tags=["auth"])
# no register router on purpose: accounts exist only when an admin creates them (see the /users routes)


@app.get("/")
def health():
    return {"status": "ok", "product": "governance"}


@app.get("/health")
def health_alias():
    # the Phase 0 boot check hits this
    return {"status": "ok", "product": "governance"}


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
    rescore = sweep.rescore_policy()
    return {"active": active_packs(user), "rescore": rescore}


# --- the other three clocks: nightly sweep + on-demand (D41) ----------------


class SweepIn(BaseModel):
    limit: int = 10


@app.post("/sweep/run")
def run_sweep(payload: SweepIn | None = None, user: User = Depends(require_admin)):
    # demo endpoint standing in for the nightly cron (plan section 5: a real
    # scheduler adds ops with no demo value). Synchronous on purpose: the demo
    # runs it pre-show and wants the report back in the response.
    limit = payload.limit if payload else 10
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit must be 1-200")
    return sweep.run_sweep(limit)


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
    state["audit"] = audit.chain(state.get("audit") or [],
                                 [f"approval_workflow: {finding_id} routed to {routing['team']} ({routing['why']})"])
    store.save(state)
    return {"finding_id": finding_id, **routing}


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

    finding["review"] = {
        "verdict": payload.verdict,
        "reason": reason,
        "by": user.email,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    # an override closes the finding; an approval CONFIRMS it, so the remediation work stays open
    if payload.verdict == "overridden":
        finding["status"] = "dismissed"
    state["audit"] = audit.chain(
        state.get("audit") or [],
        [f"reviewer_decision: {finding_id} {payload.verdict} by {user.email} ({reason or 'confirmed as raised'})"],
    )
    store.save(state)
    return {
        "finding_id": finding_id,
        "verdict": payload.verdict,
        "status": finding["status"],
        "reason": reason,
        "by": user.email,
    }


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
