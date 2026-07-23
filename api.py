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

from app import audit, precedent, store
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

store.init_db()  # make sure the assets table exists when the API boots

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_user_table()
    try:
        precedent.ensure_collection()  # label the Weaviate drawer on a fresh machine
    except Exception as e:
        print(f"[precedent] ensure_collection failed (Weaviate down?): {e}", flush=True)
    yield  # everything before the yield is startup; nothing to tear down after


app = FastAPI(title="Enterprise AI Governance API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
