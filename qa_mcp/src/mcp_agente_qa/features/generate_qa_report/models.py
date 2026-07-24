from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateQaReportInput(BaseModel):
    user_email: str | None = Field(default=None, description="Authenticated user email")
    project: str = Field(..., description="Azure DevOps project name")
    test_plan_id: int = Field(..., ge=1)
    include_evidence: bool = Field(default=True)
    report_date: str | None = Field(
        default=None, description="Optional date dd/MM/yyyy for the cover/header. Defaults to today."
    )
