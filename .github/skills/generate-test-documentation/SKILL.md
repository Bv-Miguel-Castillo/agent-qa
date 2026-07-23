---
name: generate-test-documentation
description: 'Use when the user provides a Test Plan ID and asks to generate the QA documentation / Word report for that plan (e.g. "crea la documentación del plan 96912"). Uses a single MCP tool that builds the Word report server-side.'
---

# Generate Test Documentation (Word)

Generate a formatted Word (`.docx`) QA report for a Test Plan using a SINGLE MCP tool.
The tool collects the plan data AND builds the Word report entirely server-side, so no local
commands, no PowerShell and no `.ps1` are used to build the document.

---

## Step 1 — Generate the report (single MCP tool)

Call MCP tool `generate_qa_report` with:

- `access_token`: OAuth bearer token from client (passthrough; optional)
- `project`: Azure DevOps project name
- `test_plan_id`: plan ID from user
- `include_evidence`: `true` (default)

This ONE tool does everything **server-side**: it collects the plan, User Story, suites, cases,
results and evidence, and builds the formatted Word report using the corporate template. It returns:

- `FileName` — the report file name.
- `Base64FilePath` — a temp file containing the report encoded in base64.
- `PlanId`, `PlanName`, `Hu`, `Summary` — for your response to the user.

Do NOT run `build_report.py` or any other command to build the document — the tool already built it.
If `Summary.total` is 0, inform the user and stop.

---

## Step 2 — Save the report locally

The report already exists (built by the tool). The ONLY remaining action is to save it to disk by
decoding `Base64FilePath` into `documentacion_generada/<FileName>`. Use ONLY the small paths the tool
returned — never paste or re-type the base64 content yourself.

```bash
python -c "import base64,os,sys; p,f=sys.argv[1],sys.argv[2]; os.makedirs('documentacion_generada',exist_ok=True); open(os.path.join('documentacion_generada',f),'wb').write(base64.b64decode(open(p).read()))" "<Base64FilePath>" "<FileName>"
```

Replace `<Base64FilePath>` and `<FileName>` with the exact values returned in Step 1.
`documentacion_generada` must end up containing ONLY the final `.docx`.

> Note: this step only *saves the file the tool returned* — it does not build anything, and it works
> the same whether the qa-mcp server runs locally or remotely.

---

## Step 3 — Deliver

Use `documentacion_generada/<FileName>` (the file saved in Step 2).

Then tell the user (in Spanish):

```
✅ Documentación generada: <ruta completa del .docx>
```

Include a short summary: plan, HU, total de casos, pasaron/fallaron, y cuántas evidencias se incluyeron.
Remind them to pulsar F9 sobre el índice para actualizarlo.

---

## Notes on the template (design is dynamic, sections are standard)

- **Design** (cover, logo, header, index, styles) is bundled inside the qa-mcp server. It is built
  from the reference report `./assets/plantilla_reporte.docx`. If you replace the reference with a
  new design, call MCP tool `regenerate_base_template` with:
  - `source_docx`: `./.github/skills/generate-test-documentation/assets/plantilla_reporte.docx`
  - `output_docx`: `./.github/skills/generate-test-documentation/assets/plantilla_base.docx`
- **Sections** are the standard QA report set (Introducción, Alcance, Resumen, Resultados,
  Evidencias, Conclusiones, Recomendaciones), built by the `generate_qa_report` tool server-side.

## Anti-patterns

- ❌ Rehacer el documento con `create_document` (pierde la marca corporativa).
- ❌ Cambiar título/fechas con `search_and_replace` del MCP (no alcanza text boxes / content controls).
- ❌ Construir el cuerpo con llamadas MCP `add_*` o con `build_report.py` — lo arma `generate_qa_report`.
- ❌ Re-escribir, pegar o inspeccionar el contenido base64 tú mismo (usa solo `Base64FilePath`).
- ❌ Ejecutar cualquier `.ps1` desde la skill.
- ❌ Guardar cualquier archivo temporal dentro de `documentacion_generada`; ahí SOLO va el `.docx` final.
