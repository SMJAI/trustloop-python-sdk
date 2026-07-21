"""TrustLoop Python SDK — synchronous client."""

from __future__ import annotations

import os
import functools
from typing import Any, Callable, Dict, List, Optional

import requests

from .exceptions import TrustLoopError, TrustLoopBlockedError, TrustLoopPendingError

_DEFAULT_BASE_URL = "https://trustloop-production.up.railway.app"


class TrustLoop:
    """
    TrustLoop governance client.

    Usage::

        from trustloop import TrustLoop

        tl = TrustLoop(api_key="tl_...")

        result = tl.intercept("send_email", {"to": "ceo@bank.com"})
        if not result["allowed"]:
            raise RuntimeError(result["message"])

    Or with raise_if_blocked=True::

        tl.intercept("delete_database", raise_if_blocked=True)  # raises TrustLoopBlockedError
    """

    def __init__(
        self,
        api_key: str = None,
        *,
        agent_name: str = None,
        base_url: str = None,
    ):
        self.api_key = api_key or os.environ.get("TRUSTLOOP_API_KEY")
        if not self.api_key:
            raise TrustLoopError(
                "api_key is required. Pass it directly or set TRUSTLOOP_API_KEY env var. "
                "Get your key at https://trustloop.live/signup"
            )
        self.agent_name = agent_name or os.environ.get("TRUSTLOOP_AGENT_NAME")
        self.base_url = (base_url or os.environ.get("TRUSTLOOP_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        })

    # ── Internal ─────────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, body: dict = None) -> Any:
        url = f"{self.base_url}{path}"
        resp = self._session.request(method, url, json=body)
        if not resp.ok:
            try:
                msg = resp.json().get("error") or resp.reason
            except Exception:
                msg = resp.reason
            raise TrustLoopError(msg, status=resp.status_code)
        ct = resp.headers.get("content-type", "")
        if "text/csv" in ct:
            return resp.text
        return resp.json()

    def close(self):
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ── Core Governance ───────────────────────────────────────────────────────

    def intercept(
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
        Intercept a tool call before executing it.

        Returns a dict with keys:
          - allowed (bool)
          - decision ("ALLOWED" | "BLOCKED" | "ESCALATED")
          - message (str, optional)
          - approval_id (str, optional — present when decision is ESCALATED)
          - forwarded (bool, optional — True when forward_to was used)
          - status_code (int, optional — HTTP status of the forwarded call)
          - result (any, optional — actual response from the forwarded call)

        Args:
            tool_name:        The name of the tool being called.
            args:             The arguments being passed to the tool.
            agent_name:       Override the agent name set on the client.
            raise_if_blocked: If True, raises TrustLoopBlockedError or
                              TrustLoopPendingError instead of returning.
            forward_to:       Optional dict with keys url, method, headers, body.
                              If provided and the call is ALLOWED, TrustLoop
                              forwards the request to that HTTPS endpoint and
                              returns the real response. Blocked calls are never
                              forwarded.

        Example — check only::

            result = tl.intercept("send_email", {"to": "user@co.com"})
            if result["allowed"]:
                send_email(...)

        Example — check + execute in one call::

            result = tl.intercept(
                "send_email",
                {"to": "user@co.com", "subject": "Hello"},
                forward_to={
                    "url": "https://api.resend.com/emails",
                    "method": "POST",
                    "headers": {"Authorization": "Bearer re_xxx"},
                },
            )
            # result["forwarded"] is True, result["result"] is the Resend response
        """
        payload: dict = {
            "tool_name": tool_name,
            "arguments": args or {},
        }
        name = agent_name or self.agent_name
        if name:
            payload["agent_name"] = name
        if reason:
            payload["reason"] = reason
        if forward_to:
            payload["forward_to"] = forward_to

        result = self._request("POST", "/api/intercept", payload)

        if raise_if_blocked:
            decision = result.get("decision", result.get("status", ""))
            if decision == "BLOCKED":
                raise TrustLoopBlockedError(tool_name, result.get("message"))
            if decision in ("ESCALATED", "PENDING"):
                raise TrustLoopPendingError(tool_name, result.get("approval_id"))

        return result

    # ── Decorator ─────────────────────────────────────────────────────────────

    def guard(
        self,
        tool_name: str = None,
        *,
        agent_name: str = None,
        raise_if_blocked: bool = True,
        on_block: Callable = None,
    ):
        """
        Decorator that intercepts a function with TrustLoop before running it.

        Args:
            tool_name:        Name of the tool (defaults to the function name).
            agent_name:       Override agent name for this tool.
            raise_if_blocked: Raise TrustLoopBlockedError if blocked (default True).
                              Set False to silently skip the function instead.
            on_block:         Optional callback(tool_name, result) called when blocked.

        Example::

            @tl.guard("send_email")
            def send_email(to: str, subject: str, body: str):
                ...  # only runs if TrustLoop allows it

            # Or use the function name automatically:
            @tl.guard()
            def delete_user(user_id: str):
                ...
        """
        def decorator(fn: Callable) -> Callable:
            name = tool_name or fn.__name__

            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                # Build args dict from positional + keyword args
                import inspect
                sig = inspect.signature(fn)
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                call_args = dict(bound.arguments)

                result = self.intercept(
                    name,
                    call_args,
                    agent_name=agent_name,
                    raise_if_blocked=False,
                )

                if not result.get("allowed", True):
                    if on_block:
                        return on_block(name, result)
                    if raise_if_blocked:
                        status = result.get("status", "BLOCKED")
                        if status == "PENDING":
                            raise TrustLoopPendingError(name, result.get("approval_id"))
                        raise TrustLoopBlockedError(name, result.get("message"))
                    return None  # silently skip

                return fn(*args, **kwargs)

            return wrapper
        return decorator

    # ── Audit Log ─────────────────────────────────────────────────────────────

    def get_logs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str = None,
        tool_name: str = None,
    ) -> List[dict]:
        """Fetch the audit log of all tool calls."""
        params = f"limit={limit}&offset={offset}"
        if status:
            params += f"&status={status}"
        if tool_name:
            params += f"&tool_name={tool_name}"
        return self._request("GET", f"/api/logs?{params}")

    def export_logs(self) -> str:
        """Export the full audit log as a CSV string."""
        return self._request("GET", "/api/logs/export")

    def get_stats(self) -> dict:
        """Get dashboard stats: totals, breakdown by status, monthly usage."""
        return self._request("GET", "/api/stats")

    # ── Governance Rules ──────────────────────────────────────────────────────

    def get_rules(self) -> List[dict]:
        """List all governance rules."""
        return self._request("GET", "/api/approval-rules")

    def create_rule(
        self,
        rule_text: str,
        *,
        action: str = "approve",
        approver_email: str = None,
    ) -> dict:
        """
        Create a governance rule in plain English.

        Example::

            tl.create_rule(
                "Any wire transfer over £10,000 requires human approval",
                action="approve",
                approver_email="cfo@mycompany.com",
            )
        """
        payload = {"rule_text": rule_text, "action": action}
        if approver_email:
            payload["approver_email"] = approver_email
        return self._request("POST", "/api/approval-rules", payload)

    def delete_rule(self, rule_id: str) -> dict:
        """Delete a governance rule by ID."""
        return self._request("DELETE", f"/api/approval-rules/{rule_id}")

    # ── Kill Switch ───────────────────────────────────────────────────────────

    def get_blocked_tools(self) -> List[dict]:
        """List all tools currently on the kill-switch list."""
        return self._request("GET", "/api/blocked-tools")

    def block_tool(self, tool_name: str, reason: str = "") -> dict:
        """
        Instantly block a tool. All agent calls to it will be rejected.

        Example::

            tl.block_tool("drop_table", "Emergency: DB ops disabled")
        """
        return self._request("POST", "/api/blocked-tools", {"tool_name": tool_name, "reason": reason})

    def unblock_tool(self, tool_name: str) -> dict:
        """Remove a tool from the kill-switch list."""
        from urllib.parse import quote
        return self._request("DELETE", f"/api/blocked-tools/{quote(tool_name)}")

    # ── Human Approvals ───────────────────────────────────────────────────────

    def get_pending_approvals(self) -> List[dict]:
        """List all tool calls currently awaiting human approval."""
        return self._request("GET", "/api/pending-approvals")

    def decide(self, approval_id: str, action: str) -> dict:
        """
        Approve or deny a pending tool call.

        Args:
            approval_id: The pending approval ID.
            action:      "approved" or "denied".
        """
        return self._request("POST", f"/api/pending-approvals/{approval_id}/decide", {"action": action})

    # ── Notifications ─────────────────────────────────────────────────────────

    def get_notifications(self) -> dict:
        """Get current notification settings."""
        return self._request("GET", "/api/notification-settings")

    def update_notifications(self, settings: dict) -> dict:
        """
        Update notification settings.

        Keys: notify_email, slack_webhook_url, teams_webhook_url, discord_webhook_url
        """
        return self._request("PUT", "/api/notification-settings", settings)

    # ── Static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def mcp_url(api_key: str, base_url: str = None) -> str:
        """Return the MCP SSE URL for Claude Desktop / Cline config."""
        base = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        return f"{base}/sse?api_key={api_key}"
