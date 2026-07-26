"""Navige integration for CrewAI.

Install: pip install Navige[crewai]

Usage::

    from Navige import Navige
    from Navige.integrations.crewai import governed_tool

    tl = Navige(api_key="tl_...", agent_name="my-crew")

    @governed_tool(tl)
    class SendEmailTool(BaseTool):
        name: str = "send_email"
        description: str = "Send an email to a recipient"

        def _run(self, to: str, subject: str, body: str) -> str:
            # Only reaches here if Navige allows it
            ...
"""

from __future__ import annotations

from typing import Any, Callable

from Navige.exceptions import NavigeBlockedError, NavigePendingError


def governed_tool(tl, *, agent_name: str = None, raise_if_blocked: bool = True):
    """
    Class decorator that wraps a CrewAI BaseTool with Navige governance.

    Usage::

        @governed_tool(tl)
        class MyTool(BaseTool):
            name = "my_tool"
            ...
    """
    def decorator(cls):
        original_run = cls._run

        def governed_run(self, *args, **kwargs) -> Any:
            # Build call_args from positional + keyword
            import inspect
            sig = inspect.signature(original_run)
            params = list(sig.parameters.keys())[1:]  # skip 'self'
            call_args = dict(zip(params, args))
            call_args.update(kwargs)

            result = tl.intercept(
                self.name,
                call_args,
                agent_name=agent_name,
                raise_if_blocked=False,
            )

            if not result.get("allowed", True):
                if raise_if_blocked:
                    status = result.get("status", "BLOCKED")
                    if status == "PENDING":
                        raise NavigePendingError(self.name, result.get("approval_id"))
                    raise NavigeBlockedError(self.name, result.get("message"))
                return f"[Navige] Tool '{self.name}' was blocked."

            return original_run(self, *args, **kwargs)

        cls._run = governed_run
        return cls

    return decorator


def wrap_crew_tools(tools: list, tl, *, agent_name: str = None) -> list:
    """
    Wrap a list of CrewAI tool instances with Navige governance.

    Drop-in replacement — pass the result directly to your CrewAI Agent.

    Example::

        from crewai import Agent
        from Navige.integrations.crewai import wrap_crew_tools

        tools = wrap_crew_tools([search_tool, code_tool], tl)
        agent = Agent(role="researcher", tools=tools, ...)
    """
    for tool in tools:
        original_run = tool._run.__func__ if hasattr(tool._run, "__func__") else tool._run

        def make_governed(orig, name):
            def governed(self, *args, **kwargs):
                import inspect
                try:
                    sig = inspect.signature(orig)
                    params = list(sig.parameters.keys())[1:]
                    call_args = dict(zip(params, args))
                    call_args.update(kwargs)
                except Exception:
                    call_args = {"args": args, **kwargs}

                result = tl.intercept(
                    name, call_args,
                    agent_name=agent_name,
                    raise_if_blocked=False,
                )

                if not result.get("allowed", True):
                    status = result.get("status", "BLOCKED")
                    if status == "PENDING":
                        raise NavigePendingError(name, result.get("approval_id"))
                    raise NavigeBlockedError(name, result.get("message"))

                return orig(self, *args, **kwargs)
            return governed

        import types
        tool._run = types.MethodType(make_governed(original_run, tool.name), tool)

    return tools
