from __future__ import annotations

import json
import re
from html import unescape

from .models import (
    ParseWorkitemAttachment,
    ParseWorkitemInput,
    ParseWorkitemOutput,
)


class ParseWorkitemService:
    _RE_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
    _RE_CLOSE_BLOCK = re.compile(r"</(p|div|h1|h2|h3|li)>", re.IGNORECASE)
    _RE_OPEN_LI = re.compile(r"<li[^>]*>", re.IGNORECASE)
    _RE_TAGS = re.compile(r"<[^>]+>")

    def execute(self, payload: ParseWorkitemInput) -> dict:
        with open(payload.file_path, "r", encoding="utf-8") as file_obj:
            work_item = json.load(file_obj)

        fields = work_item.get("fields") or {}
        relations = work_item.get("relations") or []

        assigned_to = self._parse_assigned_to(fields.get("System.AssignedTo"))

        output = ParseWorkitemOutput(
            Id=self._as_int(fields.get("System.Id")),
            Title=self._as_text(fields.get("System.Title")),
            State=self._as_text(fields.get("System.State")),
            AssignedTo=assigned_to,
            AreaPath=self._as_text(fields.get("System.AreaPath")),
            IterationPath=self._as_text(fields.get("System.IterationPath")),
            WorkItemType=self._as_text(fields.get("System.WorkItemType")),
            Description=self._convert_html(fields.get("System.Description")),
            AcceptanceCriteria=self._convert_html(
                fields.get("Microsoft.VSTS.Common.AcceptanceCriteria")
            ),
            Attachments=self._parse_attachments(relations),
        )
        return output.model_dump()

    @classmethod
    def _convert_html(cls, html: object) -> str:
        if html is None:
            return ""

        text = str(html)
        if not text.strip():
            return ""

        text = cls._RE_BR.sub("\n", text)
        text = cls._RE_CLOSE_BLOCK.sub("\n", text)
        text = cls._RE_OPEN_LI.sub("- ", text)
        text = cls._RE_TAGS.sub(" ", text)

        text = unescape(text)
        text = text.replace("\xa0", " ")
        text = text.replace("&nbsp;", " ")

        clean_lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(clean_lines)

    @staticmethod
    def _parse_assigned_to(value: object) -> str:
        if isinstance(value, dict):
            return str(value.get("displayName") or value.get("uniqueName") or "")
        if value is None:
            return ""
        return str(value)

    @classmethod
    def _parse_attachments(cls, relations: list[object]) -> list[ParseWorkitemAttachment]:
        attachments: list[ParseWorkitemAttachment] = []
        for relation in relations:
            if not isinstance(relation, dict):
                continue
            if relation.get("rel") != "AttachedFile":
                continue

            attributes = relation.get("attributes")
            if not isinstance(attributes, dict):
                attributes = {}

            size_raw = attributes.get("resourceSize")
            size_kb = round(cls._as_float(size_raw) / 1024, 1)

            url = cls._as_text(relation.get("url"))
            attachment_id = url.rstrip("/").rsplit("/", 1)[-1] if url else ""

            attachments.append(
                ParseWorkitemAttachment(
                    Name=cls._as_text(attributes.get("name")),
                    SizeKB=size_kb,
                    Id=attachment_id,
                )
            )
        return attachments

    @staticmethod
    def _as_text(value: object) -> str:
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _as_float(value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _as_int(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

