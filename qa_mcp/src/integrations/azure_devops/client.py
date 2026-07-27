from __future__ import annotations

from typing import Any, Dict
from urllib.parse import quote

import httpx

from core.config import env
from core.exceptions import AzureDevOpsError


class AzureDevOpsClient:
    """Simple Azure DevOps REST API client with Bearer passthrough token."""

    def __init__(self, access_token: str, user_email: str | None = None) -> None:
        self._access_token = access_token.strip()
        self._base_url = env.azure_devops_base_url.rstrip("/")
        self._api_version = env.azure_devops_api_version
        self._timeout = env.request_timeout_seconds

    @staticmethod
    def encode_project(project: str) -> str:
        return quote(project, safe="")

    def get(self, path: str, *, raw: bool = False) -> Any:
        response = self._request("GET", path)
        return response.content if raw else response.json()

    def post_json(self, path: str, body: Dict[str, Any], content_type: str = "application/json") -> Any:
        headers = {"Content-Type": content_type}
        return self._request("POST", path, json=body, headers=headers).json()

    def post_binary(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> Any:
        headers = {"Content-Type": content_type}
        return self._request("POST", path, content=data, headers=headers).json()

    def patch_json(self, path: str, body: Any, content_type: str = "application/json-patch+json") -> Any:
        headers = {"Content-Type": content_type}
        return self._request("PATCH", path, json=body, headers=headers).json()

    def download(self, path: str) -> bytes:
        return self._request("GET", path).content

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._access_token}"
        try:
            response = httpx.request(method, url, headers=headers, timeout=self._timeout, **kwargs)
        except httpx.HTTPError as exc:
            raise AzureDevOpsError(f"HTTP error calling Azure DevOps: {exc}") from exc

        if response.status_code >= 400:
            detail = response.text.strip()
            raise AzureDevOpsError(
                f"Azure DevOps API error {response.status_code} on {method} {url}: {detail}"
            )
        return response

    def with_api_version(self, path: str) -> str:
        separator = "&" if "?" in path else "?"
        return f"{path}{separator}api-version={self._api_version}"
