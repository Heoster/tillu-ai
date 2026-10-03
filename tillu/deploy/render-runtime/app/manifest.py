from typing import Literal, Any
from pydantic import BaseModel, Field

Allowed=Literal["Chat","QuickActions","ApprovalCard","SourceList","FileGrid","SyllabusTree","PlanTimeline","ProgressChart","ToolRun","PDFViewer"]
class Component(BaseModel):
    type: Allowed
    data_ref: str|None=None
    props: dict[str,Any]=Field(default_factory=dict)
class UIManifest(BaseModel):
    version: Literal[1]=1
    layout: Literal["chat","approval","study","research","files"]
    components:list[Component]
