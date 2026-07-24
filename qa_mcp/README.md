# MCP Agente QA (Python)

MCP server implemented fully in Python with modular, feature-based architecture.

## Scope implemented

- Python-only implementation (no PowerShell or Bash execution in runtime logic).
- Strict 1:1 conversion from every `.ps1` found in `assets` to one MCP tool.
- OAuth 2.0 delegated authentication with Microsoft Entra ID using Device Code Flow (MSAL).
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

## Authentication Flow (Microsoft Entra ID Device Code)

Expected flow:

1. MCP reads app registration secrets from Azure Key Vault:
  - `MCPQA-ADO-CLIENT-ID`
  - `MCPQA-ADO-TENANT-ID`
2. MCP starts device authentication with MSAL:
  - `PublicClientApplication(client_id=client_id, authority="https://login.microsoftonline.com/{tenant_id}")`
3. MSAL generates device code instructions and the user signs in with a corporate account.
4. Microsoft Entra ID returns an access token.
5. MCP validates token claims and extracts:
  - `email`
  - `tenant_id`
  - `subject`
  - `roles` and `scopes` when present
6. MCP authorizes tool execution using configured permissions per tool.
7. MCP calls Azure DevOps using `Authorization: Bearer <access_token>` and Azure DevOps enforces user delegated permissions.

No alternate auth path is active (no PAT, no static token, no forwarded token passthrough).

## Environment variables

Configure in `.env`:

Required:

- `CLIENT_ID` (managed identity or app identity that can read Azure Key Vault)
- `TENANT_ID`
- `KEY_VAULT_NAME`
- `AZURE_DEVOPS_ORGANIZATION`

Optional:
- `AZURE_DEVOPS_RESOURCE_ID` (defaults to Azure DevOps resource id)
- `AZURE_DEVOPS_API_VERSION`
- `REQUEST_TIMEOUT_SECONDS`
- `ALLOW_INSECURE_TOKEN_DECODE` (for local debugging only)
- `TOOL_PERMISSIONS` (JSON map of tool -> required permissions)
- `DEVICE_CODE_CLIENT_ID_SECRET_NAME` (default: `MCPQA-ADO-CLIENT-ID`)
- `DEVICE_CODE_TENANT_ID_SECRET_NAME` (default: `MCPQA-ADO-TENANT-ID`)

Azure Key Vault must contain:
- `MCPQA-ADO-CLIENT-ID`
- `MCPQA-ADO-TENANT-ID`

## Run locally

```bash
pip install -r requirements.txt
set PYTHONPATH=src
python main.py
```

## Run with Docker

```bash
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
