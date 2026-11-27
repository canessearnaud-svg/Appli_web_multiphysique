import secrets
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session as DbSession

from .db import SessionLocal
from .models import Session as UserSession
from .models import User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(authorization: Optional[str] = Header(default=None), db: DbSession = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="jeton manquant")
    token = authorization[len("Bearer "):]
    sess = db.query(UserSession).filter(UserSession.token == token).first()
    if sess is None:
        raise HTTPException(status_code=401, detail="jeton invalide")
    user = db.get(User, sess.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="utilisateur introuvable")
    return user


def dev_login(email: str, name: str = ""):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(email=email, name=name or email.split("@")[0])
            db.add(user)
            db.commit()
            db.refresh(user)
        token = secrets.token_hex(32)
        db.add(UserSession(token=token, user_id=user.id))
        db.commit()
        return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}
    finally:
        db.close()
