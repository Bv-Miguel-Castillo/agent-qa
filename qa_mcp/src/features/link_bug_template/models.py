from __future__ import annotations

from pydantic import BaseModel, Field


class LinkBugTemplateInput(BaseModel):
    user_email: str | None = Field(default=None, description="Authenticated user email")
    project: str = Field(..., description="Azure DevOps project name")
    bug_id: int | None = Field(default=None, ge=1)
    hu_id: int | None = Field(default=None, ge=1)
    test_plan_id: int | None = Field(default=None, ge=1)
    action: str = Field(default="link", description="link | create | update | create_or_update")

    title: str | None = None
    repro_steps_html: str | None = None
    area_path: str | None = None
    iteration_path: str | None = None
    assigned_to: str | None = None
    tags: str | None = None
    effort: float | int | None = None
    test_case_id: int | None = Field(default=None, ge=1)
