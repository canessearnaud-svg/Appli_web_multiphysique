import asyncio

import redis as redis_lib
from fastapi import Depends, FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session as DbSession

from .auth import dev_login, get_current_user, get_db
from .config import settings
from .db import SessionLocal, init_db
from .models import Diagram, Project, Run, Session as UserSession, User
from .queue import queue
from .schemas import DiagramIn, DiagramOut, ProjectIn, ProjectOut, RunIn, RunOut
from .sim.engine import run_job
from .sim.mechanics import kinematics

app = FastAPI(title="Appli web multiphysique")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/dev-login")
def login(payload: dict):
    email = payload.get("email", "")
    if not email:
        raise HTTPException(status_code=400, detail="email requis")
    return dev_login(email, payload.get("name", ""))


@app.get("/api/projects", response_model=list[ProjectOut])
def list_projects(user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return db.query(Project).filter(Project.owner_id == user.id).order_by(Project.created_at.desc()).all()


@app.post("/api/projects", response_model=ProjectOut, status_code=201)
def create_project(p: ProjectIn, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    proj = Project(owner_id=user.id, name=p.name, description=p.description)
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


@app.get("/api/projects/{pid}", response_model=ProjectOut)
def get_project(pid: int, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == pid, Project.owner_id == user.id).first()
    if proj is None:
        raise HTTPException(status_code=404, detail="projet introuvable")
    return proj


@app.get("/api/projects/{pid}/diagrams", response_model=list[DiagramOut])
def list_diagrams(pid: int, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == pid, Project.owner_id == user.id).first()
    if proj is None:
        raise HTTPException(status_code=404, detail="projet introuvable")
    return db.query(Diagram).filter(Diagram.project_id == pid).all()


@app.put("/api/projects/{pid}/diagrams/{domain}", response_model=DiagramOut)
def save_diagram(pid: int, domain: str, d: DiagramIn, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == pid, Project.owner_id == user.id).first()
    if proj is None:
        raise HTTPException(status_code=404, detail="projet introuvable")
    diagram = db.query(Diagram).filter(Diagram.project_id == pid, Diagram.domain == domain).first()
    if diagram is None:
        diagram = Diagram(project_id=pid, domain=domain, data=d.data)
        db.add(diagram)
    else:
        diagram.data = d.data
    db.commit()
    db.refresh(diagram)
    return diagram


@app.delete("/api/projects/{pid}", status_code=204)
def delete_project(pid: int, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == pid, Project.owner_id == user.id).first()
    if proj is None:
        raise HTTPException(status_code=404, detail="projet introuvable")
    db.query(Diagram).filter(Diagram.project_id == pid).delete()
    db.query(Run).filter(Run.project_id == pid).delete()
    db.delete(proj)
    db.commit()
    return None


@app.post("/api/projects/{pid}/analyze")
def analyze(pid: int, payload: dict, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == pid, Project.owner_id == user.id).first()
    if proj is None:
        raise HTTPException(status_code=404, detail="projet introuvable")
    domain = payload.get("domain")
    data = payload.get("data") or {}
    if domain == "kinematics":
        return kinematics.analyze_structure(data)
    raise HTTPException(status_code=400, detail="domaine inconnu")


@app.post("/api/projects/{pid}/runs", response_model=RunOut, status_code=201)
def create_run(pid: int, r: RunIn, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == pid, Project.owner_id == user.id).first()
    if proj is None:
        raise HTTPException(status_code=404, detail="projet introuvable")
    run = Run(project_id=pid, owner_id=user.id, type=r.type, params=r.params, status="queued")
    db.add(run)
    db.commit()
    db.refresh(run)
    queue.enqueue(run_job, run.id)
    return run


@app.get("/api/runs/{rid}", response_model=RunOut)
def get_run(rid: int, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    run = db.query(Run).filter(Run.id == rid, Run.owner_id == user.id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="run introuvable")
    return run


@app.websocket("/ws/runs/{rid}")
async def run_ws(ws: WebSocket, rid: int, token: str = ""):
    db = SessionLocal()
    sess = db.query(UserSession).filter(UserSession.token == token).first()
    run = db.query(Run).filter(Run.id == rid).first() if sess else None
    db.close()
    if run is None or sess is None or run.owner_id != sess.user_id:
        await ws.close(code=4401)
        return
    await ws.accept()
    r = redis_lib.Redis.from_url(settings.REDIS_URL)
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(f"run:{rid}")
    try:
        while True:
            msg = pubsub.get_message(timeout=0.5)
            if msg is not None:
                await ws.send_text(msg["data"].decode())
            else:
                await asyncio.sleep(0.05)
    except Exception:
        pass
    finally:
        pubsub.close()
