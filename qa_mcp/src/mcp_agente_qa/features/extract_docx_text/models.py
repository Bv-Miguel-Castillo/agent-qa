from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractDocxTextInput(BaseModel):
    file_path: str = Field(..., description="Path to DOCX file")
