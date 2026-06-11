"""TrustLoop integration for LangChain.

Install: pip install trustloop[langchain]

Usage::

    from trustloop import TrustLoop
    from trustloop.integrations.langchain import wrap_tools

    tl = TrustLoop(api_key="tl_...", agent_name="my-langchain-agent")

    # Wrap all your tools — TrustLoop intercepts every call
    tools = wrap_tools([search_tool, email_tool, db_tool], tl)

    agent = create_openai_tools_agent(llm, tools, prompt)
"""

from __future__ import annotations

from typing import Any, List, Optional, Type

from trustloop.exceptions import TrustLoopBlockedError, TrustLoopPendingError


def wrap_tools(tools: list, tl, *, agent_name: str = None, raise_if_blocked: bool = True) -> list:
    """
    Wrap a list of LangChain tools so every invocation is intercepted by TrustLoop.

    Args:
        tools:            List of LangChain BaseTool instances.
        tl:               TrustLoop client instance.
        agent_name:       Override agent name (defaults to tl.agent_name).
        raise_if_blocked: Raise TrustLoopBlockedError if a tool is blocked.

    Returns:
        New list of wrapped tools — drop-in replacement for the original list.

    Example::

        from langchain_community.tools import DuckDuckGoSearchRun
        from trustloop.integrations.langchain import wrap_tools

        tools = wrap_tools([DuckDuckGoSearchRun()], tl)
    """
    return [_wrap_single_tool(tool, tl, agent_name=agent_name, raise_if_blocked=raise_if_blocked) for tool in tools]


def _wrap_single_tool(tool, tl, *, agent_name: str = None, raise_if_blocked: bool = True):
    """Wrap a single LangChain BaseTool with TrustLoop intercept."""
    try:
        from langchain_core.tools import BaseTool
    except ImportError:
        try:
            from langchain.tools import BaseTool
        except ImportError:
            raise ImportError(
                "langchain-core is required. Install with: pip install trustloop[langchain]"
            )

    original_run = tool._run
    original_arun = tool._arun
    tool_name = tool.name

    def governed_run(*args, **kwargs) -> Any:
        # Build args dict
        call_args = {}
        if args:
            call_args["input"] = args[0] if len(args) == 1 else list(args)
        call_args.update(kwargs)

        result = tl.intercept(
            tool_name, call_args,
            agent_name=agent_name,
            raise_if_blocked=False,
        )

        if not result.get("allowed", True):
            if raise_if_blocked:
                status = result.get("status", "BLOCKED")
                if status == "PENDING":
                    raise TrustLoopPendingError(tool_name, result.get("approval_id"))
                raise TrustLoopBlockedError(tool_name, result.get("message"))
            return f"[TrustLoop] Tool '{tool_name}' was blocked."

        return original_run(*args, **kwargs)

    async def governed_arun(*args, **kwargs) -> Any:
        call_args = {}
        if args:
            call_args["input"] = args[0] if len(args) == 1 else list(args)
        call_args.update(kwargs)

        result = tl.intercept(
            tool_name, call_args,
            agent_name=agent_name,
            raise_if_blocked=False,
        )

        if not result.get("allowed", True):
            if raise_if_blocked:
                status = result.get("status", "BLOCKED")
                if status == "PENDING":
                    raise TrustLoopPendingError(tool_name, result.get("approval_id"))
                raise TrustLoopBlockedError(tool_name, result.get("message"))
            return f"[TrustLoop] Tool '{tool_name}' was blocked."

        return await original_arun(*args, **kwargs)

    tool._run = governed_run
    tool._arun = governed_arun
    return tool
