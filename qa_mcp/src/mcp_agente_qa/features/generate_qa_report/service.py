from __future__ import annotations

import base64
import os
import tempfile

from ..collect_documentation_data.models import CollectDocumentationDataInput
from ..collect_documentation_data.service import CollectDocumentationDataService
from .models import GenerateQaReportInput
from .report_builder import build_report_docx

# Word template bundled with the server (ships in the container image for remote/ACA use).
TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "plantilla_base.docx")


class GenerateQaReportService:
    """Collects the plan data and builds the QA Word report entirely server-side.

    Returns the .docx as base64 so the flow needs no local command execution and works the
    same whether the server runs locally or remotely (ACA).
    """

    def __init__(self) -> None:
        self._collector = CollectDocumentationDataService()

    def execute(self, payload: GenerateQaReportInput) -> dict:
        collect_input = CollectDocumentationDataInput(
            user_email=payload.user_email,
            project=payload.project,
            test_plan_id=payload.test_plan_id,
            include_evidence=payload.include_evidence,
            evidence_dir=None,
        )
        data = self._collector.execute(collect_input)

        out_dir = tempfile.mkdtemp(prefix="reporte_qa_")
        docx_path = build_report_docx(
            data=data,
            template_path=TEMPLATE_PATH,
            out_dir=out_dir,
            fecha=payload.report_date,
        )

        with open(docx_path, "rb") as handle:
            content_base64 = base64.b64encode(handle.read()).decode("ascii")

        # Persist the base64 to a temp file so the client decodes it from a small path instead of
        # shuttling the whole payload through the agent. We deliberately do NOT return the base64
        # inline: a ~700 KB field would make VS Code offload the tool result to a file and force the
        # agent to run an extra command just to read the summary.
        base64_path = f"{docx_path}.b64.txt"
        with open(base64_path, "w", encoding="ascii") as b64_file:
            b64_file.write(content_base64)

        return {
            "FileName": os.path.basename(docx_path),
            "Base64FilePath": base64_path,
            "PlanId": data.get("PlanId"),
            "PlanName": data.get("PlanName"),
            "Hu": data.get("Hu"),
            "Summary": data.get("Summary"),
        }
