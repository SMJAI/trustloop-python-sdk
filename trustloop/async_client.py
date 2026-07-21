"""TrustLoop Python SDK — async client (requires httpx)."""

from __future__ import annotations

import os
import functools
from typing import Any, Callable, List

from .exceptions import TrustLoopError, TrustLoopBlockedError, TrustLoopPendingError

_DEFAULT_BASE_URL = "https://trustloop-production.up.railway.app"


class AsyncTrustLoop:
    """
    Async TrustLoop governance client. Requires ``httpx``.

    Install: ``pip install trustloop[async]``

    Usage::

        from trustloop import AsyncTrustLoop

        async def main():
            async with AsyncTrustLoop(api_key="tl_...") as tl:
                await tl.intercept("send_email", {"to": "user@co.com"}, raise_if_blocked=True)
                # ... run the tool
    """

    def __init__(
        self,
        api_key: str = None,
        *,
        agent_name: str = None,
        base_url: str = None,
    ):
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for AsyncTrustLoop. "
                "Install with: pip install trustloop[async]"
            )
        self.api_key = api_key or os.environ.get("TRUSTLOOP_API_KEY")
        if not self.api_key:
            raise TrustLoopError(
                "api_key is required. Pass it directly or set TRUSTLOOP_API_KEY env var. "
                "Get your key at https://trustloop.live/signup"
            )
        self.agent_name = agent_name or os.environ.get("TRUSTLOOP_AGENT_NAME")
        self.base_url = (base_url or os.environ.get("TRUSTLOOP_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient(
            headers={"x-api-key": self.api_key, "Content-Type": "application/json"}
        )

    async def _request(self, method: str, path: str, body: dict = None) -> Any:
        url = f"{self.base_url}{path}"
        resp = await self._client.request(method, url, json=body)
        if not resp.is_success:
            try:
                msg = resp.json().get("error") or resp.reason_phrase
            except Exception:
                msg = resp.reason_phrase
            raise TrustLoopError(msg, status=resp.status_code)
        ct = resp.headers.get("content-type", "")
        if "text/csv" in ct:
            return resp.text
        return resp.json()

    async def aclose(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.aclose()

    # ── Core Governance ───────────────────────────────────────────────────────

    async def intercept(
        self,
        tool_name: str,
        args: dict = None,
        *,
        agent_name: str = None,
        reason: str = None,
        raise_if_blocked: bool = False,
        forward_to: dict = None,
    ) -> dict:
        """
        Async version of TrustLoop.intercept.

        Args:
            forward_to: Optional dict with keys url, method, headers, body.
                        If provided and ALLOWED, TrustLoop forwards the request
                        and returns the real response in result["result"].
        """
        payload: dict = {"tool_name": tool_name, "arguments": args or {}}
        name = agent_name or self.agent_name
        if name:
            payload["agent_name"] = name
        if reason:
            payload["reason"] = reason
        if forward_to:
            payload["forward_to"] = forward_to

        result = await self._request("POST", "/api/intercept", payload)

        if raise_if_blocked:
            decision = result.get("decision", result.get("status", ""))
            if decision == "BLOCKED":
                raise TrustLoopBlockedError(tool_name, result.get("message"))
            if decision in ("ESCALATED", "PENDING"):
                raise TrustLoopPendingError(tool_name, result.get("approval_id"))

        return result

    def guard(
        self,
        tool_name: str = None,
        *,
        agent_name: str = None,
        raise_if_blocked: bool = True,
        on_block: Callable = None,
    ):
        """Async decorator — wraps an async function with TrustLoop intercept."""
        def decorator(fn: Callable) -> Callable:
            name = tool_name or fn.__name__

            @functools.wraps(fn)
            async def wrapper(*args, **kwargs):
                import inspect
                sig = inspect.signature(fn)
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                call_args = dict(bound.arguments)

                result = await self.intercept(
                    name, call_args, agent_name=agent_name, raise_if_blocked=False
                )

                if not result.get("allowed", True):
                    if on_block:
                        return on_block(name, result)
                    if raise_if_blocked:
                        status = result.get("status", "BLOCKED")
                        if status == "PENDING":
                            raise TrustLoopPendingError(name, result.get("approval_id"))
                        raise TrustLoopBlockedError(name, result.get("message"))
                    return None

                return await fn(*args, **kwargs)

            return wrapper
        return decorator

    # ── All other methods (same as sync) ──────────────────────────────────────

    async def get_logs(self, *, limit=50, offset=0, status=None, tool_name=None) -> list:
        params = f"limit={limit}&offset={offset}"
        if status:
            params += f"&status={status}"
        if tool_name:
            params += f"&tool_name={tool_name}"
        return await self._request("GET", f"/api/logs?{params}")

    async def export_logs(self) -> str:
        return await self._request("GET", "/api/logs/export")

    async def get_stats(self) -> dict:
        return await self._request("GET", "/api/stats")

    async def get_rules(self) -> list:
        return await self._request("GET", "/api/approval-rules")

    async def create_rule(self, rule_text: str, *, action="approve", approver_email=None) -> dict:
        payload = {"rule_text": rule_text, "action": action}
        if approver_email:
            payload["approver_email"] = approver_email
        return await self._request("POST", "/api/approval-rules", payload)

    async def delete_rule(self, rule_id: str) -> dict:
        return await self._request("DELETE", f"/api/approval-rules/{rule_id}")

    async def get_blocked_tools(self) -> list:
        return await self._request("GET", "/api/blocked-tools")

    async def block_tool(self, tool_name: str, reason: str = "") -> dict:
        return await self._request("POST", "/api/blocked-tools", {"tool_name": tool_name, "reason": reason})

    async def unblock_tool(self, tool_name: str) -> dict:
        from urllib.parse import quote
        return await self._request("DELETE", f"/api/blocked-tools/{quote(tool_name)}")

    async def get_pending_approvals(self) -> list:
        return await self._request("GET", "/api/pending-approvals")

    async def decide(self, approval_id: str, action: str) -> dict:
        return await self._request("POST", f"/api/pending-approvals/{approval_id}/decide", {"action": action})

    async def get_notifications(self) -> dict:
        return await self._request("GET", "/api/notification-settings")

    async def update_notifications(self, settings: dict) -> dict:
        return await self._request("PUT", "/api/notification-settings", settings)
