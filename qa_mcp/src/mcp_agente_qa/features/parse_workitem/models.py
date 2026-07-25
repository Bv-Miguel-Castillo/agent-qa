from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ParseWorkitemInput(BaseModel):
    work_item: dict[str, Any] = Field(
        ...,
        description="Azure DevOps work item JSON.",
    )


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
 