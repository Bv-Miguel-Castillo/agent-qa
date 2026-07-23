---
name: read-user-story
description: 'Use when the user provides a user story ID and you need to query and fully understand its content in Azure DevOps before generating test cases. Reads fields, acceptance criteria, and all attachments in a single optimized flow.'
---

# Read and understand a user story

## EXECUTION RULES — Follow exactly, no deviations

- NEVER search for or read this skill file via terminal. It is already loaded.
- NEVER read the mcp.json file. It is not needed.
- NEVER ask the user for information that can be retrieved from Azure DevOps.
- NEVER inspect the same JSON file multiple times.
- NEVER invoke the `parse_workitem` tool more than once per work item.
- NEVER use the `parse_workitem` tool only to inspect lengths, previews, or debug the JSON.
- After the `parse_workitem` tool finishes, use ONLY its output to build the response — do NOT re-read, re-parse, re-decode, or preview the work item again.

---

## STEP 1 — Retrieve the work item

Use the Azure DevOps MCP tools exposed by the `ado-remote-mcp` server.
If the project is already known from the conversation, get the work item directly:
```
tool: get work item (ado-remote-mcp)
action: get
project: [PROJECT]
id: [WORK_ITEM_ID]
expand: All
```

If the project is NOT known, first locate the work item:

```
tool: search work item (ado-remote-mcp)
searchText: [WORK_ITEM_ID]
top: 1
```

Then get it with the same `get work item` call as above.

Never execute additional work item queries unless the retrieval fails.

---

## STEP 2 — Parse the work item

### Case A — Small response
If the MCP returns the work item inline:

- Read all fields directly.
- Do NOT run any script.
- Continue with attachments (Step 3).

### Case B — Large response

If the MCP returns `Large tool result written to file...`, use the `parse_workitem` tool from `qa_mcp` to parse the generated JSON file.

Use the tool exactly once per work item, and treat its output as the single source of truth for **Id**, **Title**, **State**, **AssignedTo**, **AreaPath**, **IterationPath**, **WorkItemType**, **Description**, **AcceptanceCriteria**, and **Attachments**.

---

## STEP 3 — Read attachments
For each attachment returned by the previous step, use the attachment tool from `ado-remote-mcp`:

```
tool: get work item attachment (ado-remote-mcp)
attachmentId: [AttachmentId]
fileName: [AttachmentName]
project: [PROJECT]
```

### File handling

| Extension | Action |
|-----------|--------|
| .md | Summarize |
| .txt | Summarize |
| .json | Summarize |
| .png, .jpg, .jpeg, .gif, .bmp, .webp | Describe image |
| .docx | Extract text with qa_mcp(extract_docx_text) |
| Others | Report filename only |

### DOCX extraction

If extraction fails, the script itself returns:

```
No se pudo extraer texto del archivo Word.
```

---

## STEP 4 — Acceptance Criteria fallback

Only if AcceptanceCriteria is empty after parsing.

Strategy 1:

```
tool: search work item (ado-remote-mcp)
searchText: [System.Title]
project: [PROJECT]
top: 1
```

If still empty:

```
tool: search wiki (ado-remote-mcp)
searchText: [System.Title]
project: [PROJECT]
top: 3
```

If still empty, stop and respond:

```
No pude obtener criterios de aceptación.

No generaré casos de prueba basados en inferencias.
```

---

## OUTPUT FORMAT (MANDATORY)

Before the summary declare:

```
Encontré [N] criterios de aceptación.

Encontré [N] archivo(s) adjunto(s).
```

## Summary of US [System.Id] to validate understanding before creating the Test Plan
### 📋 General information

| Field | Value |
|---|---|
| ID | [System.Id] |
| Type | [System.WorkItemType] |
| Title | [System.Title] |
| Project | [PROJECT] |
| Current state | [System.State] |
| Assigned to | [System.AssignedTo] |
| Priority | [Microsoft.VSTS.Common.Priority] |
| Area | [System.AreaPath] |
| Iteration | [System.IterationPath] |
| Parent | [System.Parent] |

### 🧩 Functional description
Display the cleaned content of **System.Description** as plain text.
- Remove all HTML.
- Preserve the original structure.
- If the sections **As / I want / So that** (or **Como / Quiero / Para**) exist, preserve them exactly.
- If **Background / Antecedentes** exists, preserve it as well.
- Do not summarize or omit information.

### ✅ Acceptance criteria
Display the **FULL** content of **Microsoft.VSTS.Common.AcceptanceCriteria**.
Rules:
- Include **every** acceptance criterion (CA1, CA2, CA3, CA4...).
- Preserve every **Given / When / Then** (or **Dado / Cuando / Entonces**) sentence exactly as written.
- Preserve the original ordering.
- Preserve numbered or bulleted formatting when possible.
- **Never summarize.**
- **Never truncate with "[...]".**
- **Never omit any criterion.**

### 📎 Attachments / Relations
For every attachment or relation returned by the work item, display:
- [Attachment or relation name] — [relation type]
If there are no attachments or relations, write exactly:
```
No attachments or relations registered.
```
If attachments exist and their contents were successfully processed during Step 3, after the list include:
**Attachment summaries**

For each attachment:
**[Attachment name]**
- Type
- Size
- Summary (2–5 sentences)

Do not include attachment summaries for relations that are not downloadable files.
---

## Bundled 
- qa_mcp (parse_workitem) — Parses the large work-item JSON into fields + clean Description/Acceptance Criteria + attachment list, in one pass.
- qa_mcp (extract_docx_text) — Extracts raw text from a `.docx` attachment.

 