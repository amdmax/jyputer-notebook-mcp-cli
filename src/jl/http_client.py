"""Thin httpx wrapper for Jupyter REST API."""

from __future__ import annotations

import httpx

_HTTP_TIMEOUT = 10  # seconds for REST API calls
_ERR_TRUNCATE = 200  # chars of response body shown in error messages


class JupyterError(Exception):
    pass


class JupyterClient:
    def __init__(self, url: str, token: str):
        self._base = url.rstrip("/")
        headers = {"Authorization": f"Token {token}"} if token else {}
        self._client = httpx.Client(headers=headers, timeout=_HTTP_TIMEOUT)

    def _url(self, path: str) -> str:
        return f"{self._base}{path}"

    def _get(self, path: str, **kwargs) -> dict | list:
        r = self._client.get(self._url(path), **kwargs)
        if not r.is_success:
            raise JupyterError(
                f"GET {path} -> {r.status_code}: {r.text[:_ERR_TRUNCATE]}"
            )
        return r.json()

    def _post(self, path: str, **kwargs) -> dict:
        r = self._client.post(self._url(path), **kwargs)
        if not r.is_success:
            raise JupyterError(
                f"POST {path} -> {r.status_code}: {r.text[:_ERR_TRUNCATE]}"
            )
        return r.json()

    def _delete(self, path: str) -> None:
        r = self._client.delete(self._url(path))
        if r.status_code not in (200, 204, 404):
            raise JupyterError(
                f"DELETE {path} -> {r.status_code}: {r.text[:_ERR_TRUNCATE]}"
            )

    def get_kernel(self, kernel_id: str) -> dict | None:
        r = self._client.get(self._url(f"/api/kernels/{kernel_id}"))
        if r.status_code == 404:
            return None
        if not r.is_success:
            raise JupyterError(
                f"GET /api/kernels/{kernel_id} -> {r.status_code}: {r.text[:_ERR_TRUNCATE]}"
            )
        return r.json()

    def create_kernel(self, name: str = "python3") -> dict:
        return self._post("/api/kernels", json={"name": name})

    def delete_kernel(self, kernel_id: str) -> None:
        self._delete(f"/api/kernels/{kernel_id}")

    def list_kernels(self) -> list[dict]:
        return self._get("/api/kernels")

    def list_contents(self, path: str = "") -> list[dict]:
        result = self._get(f"/api/contents/{path}")
        if isinstance(result, dict) and result.get("type") == "directory":
            return result.get("content", [])
        return [result]

    def get_notebook(self, path: str) -> dict:
        result = self._get(f"/api/contents/{path}", params={"content": "1"})
        if not isinstance(result, dict):
            raise JupyterError(f"Unexpected response for {path}")
        return result

    def upload_notebook(self, remote_path: str, content: dict) -> dict:
        payload = {
            "type": "notebook",
            "format": "json",
            "content": content,
        }
        r = self._client.put(self._url(f"/api/contents/{remote_path}"), json=payload)
        if not r.is_success:
            raise JupyterError(
                f"PUT {remote_path} -> {r.status_code}: {r.text[:_ERR_TRUNCATE]}"
            )
        return r.json()

    def list_sessions(self) -> list[dict]:
        return self._get("/api/sessions")

    def close(self) -> None:
        self._client.close()
