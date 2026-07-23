# MCP Agente QA (Python)

MCP server implemented fully in Python with modular, feature-based architecture.

## Scope implemented

- Python-only implementation (no PowerShell or Bash execution in runtime logic).
- Strict 1:1 conversion from every `.ps1` found in `assets` to one MCP tool.
- OAuth Identity Passthrough support (token provided by the client).
- Azure DevOps reusable integration modules.
- Dockerfile + docker-compose + environment variable setup.
- Basic tests including 1:1 mapping validation.

## 1:1 PowerShell -> MCP tool mapping

1. `.github/skills/generate-test-documentation/assets/collect_documentation_data.ps1`
   - MCP tool: `collect_documentation_data`
2. `.github/skills/generate-test-documentation/assets/regenerate_base_template.ps1`
   - MCP tool: `regenerate_base_template`
3. `.github/skills/report-bugs/assets/collect_plan_data.ps1`
   - MCP tool: `collect_plan_data`
4. `.github/skills/report-bugs/assets/link_bug_template.ps1`
   - MCP tool: `link_bug_template`
5. `.github/skills/read-user-story/assets/extract_docx_text.ps1`
   - MCP tool: `extract_docx_text`

No extra MCP tools were created beyond these five mapped tools.

## Architecture

```text
src/mcp_agente_qa/
  core/
    config.py
    auth.py
    exceptions.py
  integrations/azure_devops/
    client.py
  features/
    collect_documentation_data/
      models.py
      service.py
      tool.py
    regenerate_base_template/
      models.py
      service.py
      tool.py
    collect_plan_data/
      models.py
      service.py
      tool.py
    link_bug_template/
      models.py
      service.py
      tool.py
    extract_docx_text/
      models.py
      service.py
      tool.py
  tool_mapping.py
  server.py
```

## Authentication Flow (Microsoft Entra ID Token Passthrough)

Expected flow:

1. User authenticates with Microsoft Entra ID using the MCP client.
2. MCP client or Azure platform authentication forwards the delegated access token to MCP via `Authorization: Bearer ...`, `X-MS-TOKEN-AAD-ACCESS-TOKEN`, or `X-Forwarded-Access-Token`.
3. MCP validates token claims and extracts:
  - `email`
  - `tenant_id`
  - `subject`
  - `roles` and `scopes` when present
4. MCP authorizes tool execution using configured permissions per tool.
5. MCP calls Azure DevOps with the validated user token for the current request only.

Server does not run OAuth login flow, does not exchange the delegated token, and does not store user credentials.

## Environment variables

Use `.env.example` as a template.

Required for production token validation:

- `MCP_QA_TENANT_ID`
- `MCP_QA_TOKEN_AUDIENCES_CSV`
- `MCP_QA_REQUIRE_TOKEN_VALIDATION=true`
- `MCP_QA_ALLOW_INSECURE_TOKEN_DECODE=false`

Recommended for Azure container hosting:

- Enable Microsoft Entra authentication on the container ingress or upstream gateway.
- Forward the delegated access token in `Authorization`, `X-MS-TOKEN-AAD-ACCESS-TOKEN`, or `X-Forwarded-Access-Token`.
- If you rely on Azure platform auth headers, ensure the upstream component forwards an access token for the Azure DevOps resource and does not strip it before the request reaches MCP.

Optional for authorization by role/scope:

- `MCP_QA_TOOL_PERMISSIONS_JSON` (JSON map of tool -> required permissions)

Optional for local manual token testing:

- `MCP_QA_STATIC_ACCESS_TOKEN` (local fallback token when request headers and `access_token` are not provided)

Optional for Azure CLI token fallback:

- `MCP_QA_USE_AZURE_CLI_TOKEN=true`
- `MCP_QA_AZURE_CLI_RESOURCE=499b84ac-1321-427f-aa17-267ca6975798`
- `MCP_QA_AZURE_CLI_TIMEOUT_SECONDS=15`

When enabled, the server runs `az account get-access-token --resource <resource>` if no request token and no static token are available.

## Run locally

```bash
pip install -r requirements.txt
set PYTHONPATH=src
python main.py
```

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

## Tests

```bash
pytest
```

Includes validation that every `.ps1` under `assets` has exactly one MCP tool mapping.

## Notes

- This implementation reimplements PowerShell functionality in Python and does not execute original PowerShell scripts.
- For local-only debugging, you may temporarily relax validation, but production containers should always validate tenant and audience claims.
