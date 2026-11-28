import json

import redis

from ..config import settings
from ..db import SessionLocal
from ..models import Run
from .mechanics import kinematics


def run_job(run_id: int):
    r = redis.Redis.from_url(settings.REDIS_URL)
    db = SessionLocal()
    run = db.get(Run, run_id)
    if run is None:
        db.close()
        return
    run.status = "running"
    db.commit()
    r.publish(f"run:{run_id}", json.dumps({"status": "running", "progress": 0.0}))
    try:
        params = run.params or {}
        if run.type == "kinematics_four_bar":
            run.result = kinematics.run_four_bar(**params)
        elif run.type == "kinematics":
            run.result = kinematics.run_mechanism(
                params.get("diagram", {}),
                steps=int(params.get("steps", 240)),
                mode=params.get("mode", "dynamics"),
            )
        else:
            raise ValueError(f"type de run inconnu: {run.type}")
        run.status = "done"
    except Exception as exc:
        run.status = "error"
        run.result = {"error": str(exc)}
    db.commit()
    r.publish(f"run:{run_id}", json.dumps({"status": run.status, "progress": 1.0}))
    db.close()
