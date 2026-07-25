---
name: read-user-story
description: 'Use when the user provides a user story ID and you need to query and fully understand its content in Azure DevOps before generating test cases. Reads fields, acceptance criteria, and attachments using an optimized QA flow.'
---

# Read and understand a user story

## EXECUTION RULES — Follow exactly, no deviations

- NEVER search for or read this skill file via terminal. It is already loaded.
- NEVER read the mcp.json file. It is not needed.
- NEVER ask the user for information that can be retrieved from Azure DevOps.
- NEVER generate test cases before presenting the user story summary for validation.
- NEVER use raw Azure DevOps work item JSON as the source for the final response.
- ALWAYS use `parse_workitem` output as the single source of truth after normalization.
- NEVER re-read, re-process, re-decode, or reinterpret the original Azure DevOps JSON after successful parsing.
- NEVER inspect local MCP source code if a tool execution fails.
- NEVER use terminal commands to inspect temporary Copilot files.
- NEVER use `expand: All` when retrieving work items.
- NEVER invoke `parse_workitem` more than once per work item.
- NEVER use `parse_workitem` only for debugging, previews, or payload inspection.

---

# STEP 1 — Retrieve the work item

Use the Azure DevOps MCP tools exposed by the `ado-remote-mcp` server.

## If project is already known

Execute:

```
tool: get work item (ado-remote-mcp)

action: get
project: [PROJECT]
id: [WORK_ITEM_ID]

fields:
- System.Id
- System.WorkItemType
- System.Title
- System.State
- System.AssignedTo
- Microsoft.VSTS.Common.Priority
- System.AreaPath
- System.IterationPath
- System.Description
- Microsoft.VSTS.Common.AcceptanceCriteria

expand:
Relations
```

## If project is NOT known

First locate the work item:

```
tool: search work item (ado-remote-mcp)

searchText:
[WORK_ITEM_ID]

top:
1
```

Then execute the optimized `get work item` call.

## Retrieval rules

- Do not use `expand: All`.
- Do not request unnecessary Azure DevOps metadata.
- Do not retrieve revisions, history, identity metadata, or unrelated links.
- Retrieve only information required for QA analysis.

---

# STEP 2 — Normalize the work item

After retrieving the work item, ALWAYS invoke:

```
tool: parse_workitem (qa_mcp)
```

Input:

```
work_item:
[FULL JSON OBJECT RETURNED BY ado-remote-mcp]
```

The purpose of this step is to normalize Azure DevOps information before analysis.

The output of `parse_workitem` is the only source of truth for:

- Id
- Title
- State
- AssignedTo
- AreaPath
- IterationPath
- WorkItemType
- Description
- AcceptanceCriteria
- Attachments metadata

After `parse_workitem` succeeds:

- NEVER use the original Azure DevOps response.
- NEVER manually extract fields from the raw response.
- NEVER manually decode HTML.
- NEVER reinterpret acceptance criteria from the original payload.

---

# STEP 3 — Process attachments

Use only attachments returned by:

```
parse_workitem.Attachments
```

For each attachment execute:

```
tool: get work item attachment (ado-remote-mcp)

attachmentId:
[AttachmentId]

fileName:
[AttachmentName]

project:
[PROJECT]
```

---

# Attachment processing rules

| Extension | Action |
|---|---|
| .md | Summarize |
| .txt | Summarize |
| .json | Summarize |
| .png | Describe image |
| .jpg | Describe image |
| .jpeg | Describe image |
| .gif | Describe image |
| .bmp | Describe image |
| .webp | Describe image |
| .docx | Use qa_mcp(extract_docx_text) |
| Others | Report filename only |

---

# DOCX extraction rules

For `.docx` attachments use:

```
tool: extract_docx_text (qa_mcp)
```

If extraction fails, use exactly:

```
No se pudo extraer texto del archivo Word.
```

Do not:

- Try alternative extraction methods.
- Read the document manually.
- Use external parsers.

---

# STEP 4 — Acceptance Criteria validation

Only evaluate:

```
parse_workitem.AcceptanceCriteria
```

Never inspect:

```
Microsoft.VSTS.Common.AcceptanceCriteria
```

from the original Azure DevOps response after parsing.

---

## If Acceptance Criteria is empty

Try:

```
tool: search work item (ado-remote-mcp)

searchText:
[Title]

project:
[PROJECT]

top:
1
```

If still empty:

```
tool: search wiki (ado-remote-mcp)

searchText:
[Title]

project:
[PROJECT]

top:
3
```

If no acceptance criteria are found:

Respond exactly:

```
No pude obtener criterios de aceptación.

No generaré casos de prueba basados en inferencias.
```

---

# OUTPUT FORMAT — Mandatory

Before generating the summary:

```
Encontré [N] criterios de aceptación.

Encontré [N] archivo(s) adjunto(s).
```

---

# Summary of US [Id] to validate understanding before creating the Test Plan

## 📋 General information

| Field | Value |
|---|---|
| ID | [Id] |
| Type | [WorkItemType] |
| Title | [Title] |
| Project | [PROJECT] |
| Current state | [State] |
| Assigned to | [AssignedTo] |
| Priority | [Priority] |
| Area | [AreaPath] |
| Iteration | [IterationPath] |

---

# 🧩 Functional description

Display the complete content returned by:

```
parse_workitem.Description
```

Rules:

- Do not summarize.
- Do not omit information.
- Preserve original structure.
- Preserve sections:
  - Como / Quiero / Para
  - As / I want / So that
  - Background
  - Antecedentes

---

# ✅ Acceptance criteria

Display the complete content returned by:

```
parse_workitem.AcceptanceCriteria
```

Rules:

- Include all acceptance criteria.
- Preserve CA numbering.
- Preserve original order.
- Preserve:
  - Given / When / Then
  - Dado / Cuando / Entonces
- Preserve bullets and numbering.
- Never summarize.
- Never truncate.
- Never replace with interpretations.

---

# 📎 Attachments and relations

Display every attachment:

```
[Attachment name] — AttachedFile
```

If there are no attachments:

```
No attachments registered.
```

For processed attachments include:

```
## Attachment summaries

[Attachment name]

- Type:
- Size:
- Summary:
```

Rules:

- Do not summarize non-file relations.
- Do not include unavailable attachment content.

---

# Failure handling

If any MCP tool fails:

1. Do not inspect local source code.
2. Do not read implementation files.
3. Do not use terminal commands.
4. Report the failure.
5. Retry only with a corrected tool input.

---

# Bundled tools

## qa_mcp — parse_workitem

Purpose:

Normalize an Azure DevOps work item JSON object.

Responsibilities:

- Clean Description.
- Clean Acceptance Criteria.
- Extract attachment metadata.
- Return a flat QA-friendly object.

It does NOT:

- Read local files.
- Receive filesystem paths.
- Access Copilot temporary resources.

---

## qa_mcp — extract_docx_text

Purpose:

Extract text from `.docx` Azure DevOps attachments.