from __future__ import annotations

from pydantic import BaseModel, Field


class CollectPlanDataInput(BaseModel):
    user_email: str | None = Field(default=None, description="Authenticated user email")
    access_token: str | None = Field(
        default=None,
        description="OAuth bearer token from client passthrough or Azure platform auth headers.",
    )
    project: str = Field(..., description="Azure DevOps project name")
    test_plan_id: int = Field(..., ge=1)
    include_evidence_upload: bool = Field(default=True)
    evidence_dir: str | None = Field(default=None)
