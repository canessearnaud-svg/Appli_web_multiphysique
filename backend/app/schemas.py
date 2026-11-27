import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ProjectIn(BaseModel):
    name: str
    description: str = ""


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    created_at: dt.datetime


class DiagramIn(BaseModel):
    domain: str
    data: dict = {}


class DiagramOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    domain: str
    data: dict
    updated_at: dt.datetime


class RunIn(BaseModel):
    type: str
    params: dict = {}


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    status: str
    params: Optional[dict]
    result: Optional[Any]
    created_at: dt.datetime
