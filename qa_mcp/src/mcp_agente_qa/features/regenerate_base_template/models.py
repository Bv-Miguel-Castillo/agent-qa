from __future__ import annotations

from pydantic import BaseModel, Field


class RegenerateBaseTemplateInput(BaseModel):
    source_docx: str = Field(..., description="Path to plantilla_reporte.docx")
    output_docx: str = Field(..., description="Path to output plantilla_base.docx")
