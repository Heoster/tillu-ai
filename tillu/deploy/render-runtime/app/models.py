from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Literal

class Risk(str, Enum):
    read = "read"
    write = "write"
    external = "external"
    sensitive = "sensitive"

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    conversation_id: str | None = None

class PlanCall(BaseModel):
    capability: str
    args: dict[str, Any] = {}

class ActionPlan(BaseModel):
    id: str
    title: str
    summary: str
    steps: list[str]
    calls: list[PlanCall] = []
    risk: Risk
    needs_approval: bool
    status: Literal["proposed", "approved", "running", "done", "failed"] = "proposed"

class ApprovalRequest(BaseModel):
    approved: bool

class ProgressUpdate(BaseModel):
    status: Literal["not_started", "learning", "practiced", "mastered", "revision_due"]
    confidence: int = Field(ge=0, le=100)

class Job(BaseModel):
    id: str
    kind: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int = 0
    payload: dict[str, Any] = {}
    result: dict[str, Any] | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class DownloadRequest(BaseModel):
    url: str
    title: str | None = None

class DocumentQuery(BaseModel):
    question: str = Field(min_length=2,max_length=2000)
    file_id: str | None = None
class TaskCreate(BaseModel):
    title: str = Field(min_length=1,max_length=240)
    subject: str | None = None
    due_at: str | None = None
    priority: int = Field(default=2,ge=1,le=3)
class TaskStatus(BaseModel):
    status: Literal["todo","doing","done"]

class SourceCreate(BaseModel):
    url: str

class EventCreate(BaseModel):
    title: str = Field(min_length=1,max_length=240)
    subject: str | None = None
    start_at: str
    end_at: str | None = None
    reminder_minutes: int = Field(default=15,ge=0,le=10080)

class NoteCreate(BaseModel):
    title: str = Field(default="Untitled note",min_length=1,max_length=240)
    content: str = Field(default="",max_length=200000)
    tags: str = "[]"
class NoteUpdate(BaseModel):
    title: str | None = Field(default=None,max_length=240)
    content: str | None = Field(default=None,max_length=200000)
    canvas_data: str | None = Field(default=None,max_length=5000000)
    tags: str | None = None
class NoteAIRequest(BaseModel):
    instruction: str = Field(min_length=2,max_length=2000)
    content: str = Field(default="",max_length=100000)

class BrowserAsk(BaseModel):
    question: str = Field(min_length=2,max_length=2000)
    title: str = Field(default="Web page",max_length=300)
    url: str = Field(max_length=2000)
    content: str = Field(max_length=50000)

class AutomationCreate(BaseModel):
    name: str = Field(min_length=2,max_length=160)
    trigger_type: Literal["schedule","manual","event"] = "schedule"
    schedule: str | None = "0 7 * * *"
    action_type: Literal["daily_brief","weather_brief","news_digest","study_review","weekly_audit","nightly_backup"] = "daily_brief"
    timezone: str = "Asia/Kolkata"
    config: dict[str, Any] = {}
    retry_policy: dict[str, Any] = {"max_attempts":3,"base_delay_seconds":60}
    enabled: bool = True
class AutomationUpdate(BaseModel):
    name: str | None = None
    schedule: str | None = None
    enabled: bool | None = None
