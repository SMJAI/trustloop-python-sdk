class TrustLoopError(Exception):
    """Raised when TrustLoop returns an error or blocks a tool call."""

    def __init__(self, message: str, status: int = None, tool_name: str = None):
        super().__init__(message)
        self.status = status
        self.tool_name = tool_name


class TrustLoopBlockedError(TrustLoopError):
    """Raised when a tool call is blocked by a governance rule or kill-switch."""

    def __init__(self, tool_name: str, reason: str = None):
        msg = f"Tool '{tool_name}' was blocked by TrustLoop"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, status=403, tool_name=tool_name)
        self.reason = reason


class TrustLoopPendingError(TrustLoopError):
    """Raised when a tool call requires human approval before proceeding."""

    def __init__(self, tool_name: str, approval_id: str = None):
        msg = f"Tool '{tool_name}' requires human approval"
        super().__init__(msg, status=202, tool_name=tool_name)
        self.approval_id = approval_id
