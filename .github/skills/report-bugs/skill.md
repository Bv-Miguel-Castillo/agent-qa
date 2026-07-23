---
name: report-bugs
description: 'Use when the user provides a Test Plan ID and the agent needs to query failed test cases and create or update bugs in Azure DevOps.'
---

# Create bugs from failed test cases

## CRITICAL RULES
- Only create bugs for **Failed** test cases.
- Blocked → notify the user, do not create a bug.
- Not Applicable → notify the user, ignore the test case.
- Always inherit `AreaPath`, `IterationPath`, and `AssignedTo` from the User Story.
- Always set `Effort = 0`.
- Never read MCP cache files or workspace storage JSON files.
- All data must come directly from **MCP Agente QA** tool calls or Azure DevOps REST API responses.
- Use only the tools exposed by **MCP Agente QA**. Do not attempt to discover or execute scripts, local files, or workspace assets.
- Never run `*.ps1`, `az`, `pwsh`, `powershell`, shell scripts, or ad-hoc REST commands for this flow.
- Do not inspect or execute files under `assets/` during bug reporting execution.
- Required execution path for this skill: `collect_plan_data` then `link_bug_template`.

---

## Step 1 — Collect ALL data in a single call

Use the **MCP Agente QA** tool:

**Tool:** `collect_plan_data`
Parameters:

- `project` → Azure DevOps project name (plain text, e.g. `Confa`).
- `test_plan_id` → Test Plan ID provided by the user.
- `user_email` → Optional. Preferred when available.
- `access_token` → Optional. If omitted, MCP resolves token via request headers or `MCP_QA_STATIC_ACCESS_TOKEN`.

This tool returns a single JSON containing all required information. Do **not** make additional MCP or REST calls for information already included in the response.

Expected JSON:
```json
{
  "PlanId": "...",
  "PlanName": "...",
  "Hu": {
    "Id": 0,
    "Title": "..",
    "AreaPath": "..",
    "IterationPath": "..",
    "AssignedTo": ".."
  },
  "Summary": {
    "failed": 0,
    "passed": 0,
    "blocked": 0,
    "notApplicable": 0,
    "unspecified": 0
  },
  "FailedCases": [
    {
      "Suite": 0,
      "TcId": 0,
      "TcName": "..",
      "RunId": 0,
      "ResultId": 0,
      "Comment": "execution comment",
      "ExistingBugId": "id or null",
      "Steps": {
        "Actions": [".."],
        "Expected": [".."]
      },
      "EvidenceUrls": ["wit attachment url"]
    }
  ]
}
```

How to use the response:

- Use `Summary` to report execution counts.
- If `Summary.failed == 0`, inform the user and stop.
- Use `Hu` to populate:
  - `AreaPath`
  - `IterationPath`
  - `AssignedTo`
- For every element in `FailedCases`:
  - If `ExistingBugId` is present → update the existing bug.
  - Otherwise → create a new bug.
  - `Steps.Actions` → PASOS.
  - `Comment` → RESULTADOS.
    - If empty, use: `"Sin comentarios registrados en el caso de prueba."`
  - `Steps.Expected` → RESULTADOS ESPERADOS.
  - `EvidenceUrls` → EVIDENCIA.
- Blocked and Not Applicable cases are only reported; never create bugs for them.

---

## Step 2 — Create bug
Use the **MCP Agente QA** tool:

**Tool:** `link_bug_template`
Parameters:
- `project`: `[PROJECT]`
- `action`: `"create"`
- `title`: `"Bug - [TEST_CASE_TITLE]"`
- `repro_steps_html`: `[HTML]`
- `assigned_to`: `[HU_ASSIGNED_TO]`
- `area_path`: `[HU_AREA_PATH]`
- `iteration_path`: `[HU_ITERATION_PATH]`
- `effort`: `0`
- `tags`: `"QA; Plan-[TEST_PLAN_ID]"`
- `hu_id`: `[HU_ID]`
- `test_plan_id`: `[TEST_PLAN_ID]`
- `user_email`: optional
- `access_token`: optional

### ReproSteps HTML

```html
<h3>PASOS</h3>
<ol>
  <li>[Steps.Actions]</li>
</ol>

<h3>RESULTADOS</h3>
<ol>
  <li>[Comment]</li>
</ol>

<h3>RESULTADOS ESPERADOS</h3>
<ol>
  <li>[Steps.Expected]</li>
</ol>

<h3>EVIDENCIA</h3>
<div><img src="[EvidenceUrls]" /></div>
```
Rules:
- Order must always be:
  - PASOS
  - RESULTADOS
  - RESULTADOS ESPERADOS
  - EVIDENCIA
- Never invent steps or expected results.
- RESULTADOS always comes from `Comment`.
- Omit the EVIDENCIA section if there are no evidence URLs.
- Never leave empty sections.
- No emojis.
After creating the bug:

Use the **MCP Agente QA** tool again:

**Tool:** `link_bug_template`
Parameters:
- `project`: `[PROJECT]`
- `action`: `"link"`
- `bug_id`: `[BUG_ID]`
- `hu_id`: `[HU_ID]`
- `test_plan_id`: `[TEST_PLAN_ID]`
- `test_case_id`: `[TEST_CASE_ID]`
- `user_email`: optional
- `access_token`: optional

This tool associates the Bug with the corresponding User Story.

---

## Step 3 — Update existing bug
Use the **MCP Agente QA** tool:

**Tool:** `link_bug_template`
Parameters:
- `project`: `[PROJECT]`
- `action`: `"update"`
- `bug_id`: `[EXISTING_BUG_ID]`
- `title`: `"Bug - [TEST_CASE_TITLE]"`
- `repro_steps_html`: `[HTML]`
- `assigned_to`: `[HU_ASSIGNED_TO]`
- `area_path`: `[HU_AREA_PATH]`
- `iteration_path`: `[HU_ITERATION_PATH]`
- `effort`: `0`
- `tags`: `"QA; Plan-[TEST_PLAN_ID]"`
- `user_email`: optional
- `access_token`: optional

Inform the user that the bug already existed and was updated.

---

## Summary to show the user
| Test Case | Action | Bug ID | Title |
|-----------|--------|--------|-------|
| [TC_TITLE] | Created / Updated | [BUG_ID] | [BUG_TITLE] |

🚫 Blocked test cases: [N]
⬜ Not Applicable test cases: [N]
