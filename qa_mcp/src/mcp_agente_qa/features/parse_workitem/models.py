from __future__ import annotations

from pydantic import BaseModel, Field


class ParseWorkitemInput(BaseModel):
    file_path: str = Field(..., description="Path to Azure DevOps work item JSON file")


class ParseWorkitemAttachment(BaseModel):
    Name: str
    SizeKB: float
    Id: str


class ParseWorkitemOutput(BaseModel):
    Id: int | None
    Title: str
    State: str
    AssignedTo: str
    AreaPath: str
    IterationPath: str
    WorkItemType: str
    Description: str
    AcceptanceCriteria: str
    Attachments: list[ParseWorkitemAttachment]
