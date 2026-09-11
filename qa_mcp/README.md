# MCP Agente QA

**MCP (Model Context Protocol)** es un protocolo estándar que permite a un agente de IA (como GitHub Copilot o Claude) invocar herramientas externas de forma estructurada. Este proyecto implementa un **servidor MCP** en Python que expone un conjunto de herramientas para automatizar tareas de QA (Quality Assurance) contra Azure DevOps: crear y actualizar Test Plans, generar Test Cases a partir de historias de usuario, reportar bugs desde resultados de pruebas fallidas, y generar documentación de QA.

En otras palabras: es el backend que le da al agente de QA la capacidad de "hablar" con Azure DevOps (leer work items, Test Plans, crear bugs, etc.) en nombre del usuario autenticado, reemplazando el flujo anterior basado en scripts de PowerShell por una arquitectura modular en Python.

## Alcance funcional

El agente de QA permite, mediante lenguaje natural, ejecutar el siguiente flujo de trabajo sobre Azure DevOps:

- **Leer y entender historias de usuario**: consultar una User Story y sus criterios de aceptación.
- **Crear y actualizar Test Plans**: generar un plan de pruebas asociado a una historia de usuario.
- **Generar Test Cases**: crear casos de prueba a partir de los criterios de aceptación de la historia.
- **Recolectar resultados de ejecución**: obtener los resultados (pasa/falla) de los Test Cases de un Test Plan.
- **Reportar Bugs**: crear work items de tipo Bug en Azure DevOps a partir de los Test Cases fallidos, incluyendo evidencia.
- **Generar documentación de QA**: producir el reporte/documento de QA (Word) a partir de la información recolectada del Test Plan.

## Stack y arquitectura técnica

- Lenguaje: Python (no hay ejecución de PowerShell ni Bash en tiempo de ejecución; toda la lógica es código Python nativo).
- Autenticación: OAuth 2.0 delegado con Microsoft Entra ID, Authorization Code Flow + PKCE (MSAL).
- Integración: módulos reutilizables para consumir la API REST de Azure DevOps.
- Empaquetado: Dockerfile + docker-compose, configurados con variables de entorno.
- Pruebas: suite de pytest en `qa_mcp/tests/`.

## Herramientas MCP expuestas

| Herramienta MCP | Función |
|---|---|
| `parse_workitem` | Consulta y estructura los datos de una User Story (campos, criterios de aceptación) |
| `extract_docx_text` | Extrae texto de adjuntos `.docx` de un work item |
| `collect_plan_data` | Recolecta datos de un Test Plan y sus Test Cases (incluyendo resultados de ejecución) |
| `link_bug_template` | Crea un Bug en Azure DevOps a partir de un Test Case fallido |
| `collect_documentation_data` | Recolecta la información necesaria para generar el reporte de QA |
| `regenerate_base_template` | Regenera la plantilla base usada en el reporte de QA |
| `generate_qa_report` | Genera el documento/reporte de QA (Word) a partir de los datos recolectados del Test Plan |

## Arquitectura

```text
qa_mcp/src/
  core/
    config.py
    auth.py
    exceptions.py
    enviroment/
    secrets/
  integrations/
    azure_devops/
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
    generate_qa_report/
      models.py
      report_builder.py
      service.py
      tool.py
    parse_workitem/
      models.py
      service.py
      tool.py
  tool_mapping.py
  server.py
```

## Flujo de autenticación (Microsoft Entra ID Authorization Code + PKCE)

Flujo esperado:

1. El MCP lee los secretos del registro de aplicación desde Azure Key Vault:
  - `MCPQA-ADO-CLIENT-ID`
  - `MCPQA-ADO-TENANT-ID`
2. El MCP inicia el flujo OAuth 2.0 Authorization Code + PKCE con MSAL:
  - `PublicClientApplication(client_id=client_id, authority="https://login.microsoftonline.com/{tenant_id}")`
3. El MCP abre la página de inicio de sesión de Microsoft Entra ID en el navegador.
4. El usuario inicia sesión con una cuenta corporativa de Microsoft.
5. Microsoft Entra ID devuelve un Authorization Code a través del callback local.
6. El MCP intercambia el Authorization Code por un Access Token.
7. El MCP valida los claims del token y extrae:
  - `email`
  - `tenant_id`
  - `subject`
  - `roles` y `scopes` cuando estén presentes
8. El MCP autoriza la ejecución de herramientas según los permisos configurados por herramienta.
9. El MCP llama a Azure DevOps usando `Authorization: Bearer <access_token>` y Azure DevOps aplica los permisos delegados del usuario.

Notas para ejecución headless o en Docker:

- Si el proceso no puede abrir el navegador automáticamente, abre la URL de Entra ID manualmente y continúa el flujo.
- Asegúrate de que el callback local sea accesible desde el navegador del usuario.
- En docker compose, expón el puerto de callback `8400` y mantén `ENTRA_REDIRECT_URI=http://localhost:8400/callback`.
- El App Registration debe tener registrado `http://localhost:8400/callback` como Redirect URI de tipo "Mobile and desktop applications" para que el flujo de login funcione.

No hay ningún camino de autenticación alterno activo (sin PAT, sin token estático, sin passthrough de token reenviado).

## Identidad para acceder a Azure Key Vault (secretos de la aplicación)

Esto es independiente de la autenticación del usuario descrita arriba: es la identidad que usa el propio MCP para leer los secretos `MCPQA-ADO-CLIENT-ID` / `MCPQA-ADO-TENANT-ID` desde Azure Key Vault. El código usa `DefaultAzureCredential`, que prueba credenciales en este orden y no requiere cambios de código entre entornos:

1. **Variables de entorno** (`AZURE_CLIENT_ID` + `AZURE_CLIENT_SECRET` + `AZURE_TENANT_ID`) — usado hoy en desarrollo local vía `.env`.
2. **Managed Identity** — usado en producción (Azure Container Apps).
3. **Azure CLI** (`az login`) — usado como respaldo local si no hay secreto configurado.

Para producción con identidad administrada (recomendado por seguridad, sin secretos embebidos):

1. Crear una **User-Assigned Managed Identity** en Azure.
2. Asignarla al Azure Container App donde corre el MCP.
3. Otorgarle el rol RBAC `Key Vault Secrets User` sobre el Key Vault (`KEY_VAULT_NAME`).
4. Configurar `AZURE_CLIENT_ID` en el Container App con el **Client ID de la Managed Identity** (no el del App Registration de usuario).
5. **No definir `AZURE_CLIENT_SECRET`** en el entorno de producción — su ausencia hace que `DefaultAzureCredential` pase automáticamente a Managed Identity.

## Permisos requeridos y principio de mínimo privilegio (Least Privilege / RBAC)

Este MCP actúa siempre en nombre del usuario autenticado (flujo delegado), nunca con permisos a nivel de aplicación. Los permisos configurados en el App Registration (`app-mcp-qa-ado`) son exclusivamente **delegados**:

| API | Permiso | Tipo | Descripción | Admin consent requerido |
|---|---|---|---|---|
| Azure DevOps | `user_impersonation` | Delegado | Acceso completo a Visual Studio Team Services REST API en nombre del usuario | No |
| Azure DevOps | `vso.test` | Delegado | Test management (lectura) | No |
| Azure DevOps | `vso.test_write` | Delegado | Test management (lectura y escritura) | No |
| Azure DevOps | `vso.work` | Delegado | Lectura de work items | No |
| Microsoft Graph | `User.Read` | Delegado | Iniciar sesión y leer el perfil del usuario | No |

**No se asignan permisos a nivel de aplicación (Application permissions)** — el MCP nunca actúa con una identidad propia sin un usuario detrás; toda operación queda acotada a lo que el usuario autenticado ya puede hacer en Azure DevOps.

Para que el flujo funcione correctamente, el usuario que inicia sesión debe contar, como mínimo, con permisos sobre el **Test Plan** correspondiente en Azure DevOps (lectura y creación de test cases/work items según la operación), asignados únicamente en el alcance necesario (proyecto/Test Plan), evitando privilegios adicionales.

Referencias:
- [Manage access to resources in Azure - Cloud Adoption Framework](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/considerations/roles)
- [About permissions and security groups - Azure DevOps](https://learn.microsoft.com/azure/devops/organizations/security/about-permissions)
- [Permissions, licensing, and access for manual testing - Azure Test Plans](https://learn.microsoft.com/azure/devops/test/wi-test-plan-permissions)

## Variables de entorno

Configura en `.env` (usa `.env.example` como plantilla, copiándolo y llenando los valores reales; `.env.example` solo contiene los nombres de las variables sin valores sensibles):

Requeridas:

- `AZURE_CLIENT_ID` (identidad administrada o de aplicación que puede leer Azure Key Vault)
- `AZURE_TENANT_ID`
- `KEY_VAULT_NAME`
- `AZURE_DEVOPS_ORGANIZATION`

Opcionales:
- `AZURE_DEVOPS_RESOURCE_ID` (por defecto usa el resource id de Azure DevOps)
- `AZURE_DEVOPS_API_VERSION`
- `REQUEST_TIMEOUT_SECONDS`
- `ALLOW_INSECURE_TOKEN_DECODE` (solo para depuración local)
- `TOOL_PERMISSIONS` (mapa JSON de herramienta -> permisos requeridos)
- `ENTRA_REDIRECT_URI` (por defecto: `http://localhost:8400/callback`)
- `AUTH_CODE_TIMEOUT_SECONDS` (por defecto: `180`)

Azure Key Vault debe contener:
- `MCPQA-ADO-CLIENT-ID`
- `MCPQA-ADO-TENANT-ID`

## Ejecutar localmente

```bash
pip install -r requirements.txt
set PYTHONPATH=src
python main.py
```

## Ejecutar con Docker

```bash
docker compose up --build
```

## Pruebas

```bash
pytest
```

Incluye la validación de que cada `.ps1` bajo `assets` tiene exactamente un mapeo de herramienta MCP.

## Notas

- Esta implementación reimplementa la funcionalidad de PowerShell en Python y no ejecuta los scripts de PowerShell originales.
- Para depuración exclusivamente local, se puede relajar temporalmente la validación, pero los contenedores de producción siempre deben validar los claims de tenant y audiencia.
