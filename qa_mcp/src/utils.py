from __future__ import annotations

import html
import re
import xml.etree.ElementTree as et


def clean_html(raw: str | None) -> str:
    if not raw:
        return ""
    text = re.sub(r"<br\\s*/?>", "\n", raw, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|h1|h2|h3|li|tr)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text).replace("&nbsp;", " ")
    lines = [re.sub(r"\s{2,}", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def clean_for_bug_text(raw: str | None) -> str:
    text = clean_html(raw)
    text = re.sub(r"[\U00010000-\U0010FFFF]", "", text)
    text = re.sub(r"[\u2190-\u27BF\u2B00-\u2BFF\uFE0F]", "", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def parse_steps_xml(steps_xml: str | None) -> dict[str, list[str]]:
    result = {"Actions": [], "Expected": []}
    if not steps_xml:
        return result
    try:
        root = et.fromstring(steps_xml)
    except et.ParseError:
        return result

    for step in root.findall("step"):
        values = step.findall("parameterizedString")
        if len(values) >= 1:
            action_text = clean_for_bug_text(values[0].text)
            if action_text:
                result["Actions"].append(action_text)
        if len(values) >= 2:
            expected_text = clean_for_bug_text(values[1].text)
            if expected_text:
                result["Expected"].append(expected_text)
    return result


def safe_file_slug(value: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^\\w\\-]", "_", value or "")
    if len(slug) > max_len:
        return slug[:max_len]
    return slug
