# navige-sdk

Python SDK for [Navige](https://navige.ai) — governance, audit trail, and kill-switch for AI agents.

Intercept every tool call your agent makes. Log it. Block dangerous actions. Require human approval. Works with LangChain, CrewAI, AutoGen, or any custom Python agent.

## Install

```bash
pip install navige-sdk
```

With async support:
```bash
pip install navige-sdk[async]
```

With LangChain integration:
```bash
pip install navige-sdk[langchain]
```

With CrewAI integration:
```bash
pip install navige-sdk[crewai]
```

Everything:
```bash
pip install navige-sdk[all]
```

## Quick start

Get your free API key at [navige.ai/signup](https://navige.ai/signup).

```python
from navige import Navige

tl = Navige(api_key="tl_your_key_here", agent_name="my-agent")

# Check before running any tool
result = tl.intercept("send_email", {"to": "ceo@bank.com", "body": "..."})
if not result["allowed"]:
    raise RuntimeError(result["message"])

# ... run the tool
```

Or set your key as an env var and let the SDK find it:

```bash
export NAVIGE_API_KEY="tl_your_key_here"
export NAVIGE_AGENT_NAME="my-agent"
```

```python
tl = Navige()  # reads from env
```

## Usage

### Manual intercept

```python
result = tl.intercept("delete_database", {"table": "users"})

# result = {
#   "allowed": False,
#   "status": "BLOCKED",
#   "message": "Matched rule: block destructive database operations"
# }
```

### Agent reason field

Pass a plain English explanation of why the agent is taking an action. The reason is stored in the audit log and shown in the approval email so the human approver sees intent, not just raw arguments. PII is masked before storage.

```python
result = tl.intercept(
    "transfer_funds",
    {"to_account": "GB29NWBK60161331926819", "amount": 5000},
    reason="User requested urgent payment to cover supplier invoice INV-0042 due today",
)
```

### Auto-raise on block

```python
from navige import Navige, NavigeBlockedError, NavigePendingError

try:
    tl.intercept("transfer_funds", {"amount": 50000}, raise_if_blocked=True)
except NavigeBlockedError as e:
    print(f"Blocked: {e}")
except NavigePendingError as e:
    print(f"Waiting for approval: {e.approval_id}")
```

### @tl.guard() decorator

```python
@tl.guard("send_email")
def send_email(to: str, subject: str, body: str):
    # Only runs if Navige allows it
    ...

@tl.guard()  # uses function name as tool name
def delete_user(user_id: str):
    ...
```

### Async

```python
from navige import AsyncNavige

async with AsyncNavige(api_key="tl_...") as tl:
    await tl.intercept("post_tweet", {"text": "Hello world"}, raise_if_blocked=True)

    @tl.guard("send_email")
    async def send_email(to, subject, body):
        ...
```

## LangChain

```python
from navige import Navige
from navige.integrations.langchain import wrap_tools

tl = Navige(api_key="tl_...", agent_name="langchain-agent")

# Wrap all tools — one line, zero boilerplate
tools = wrap_tools([search_tool, email_tool, db_tool], tl)

agent = create_openai_tools_agent(llm, tools, prompt)
```

## CrewAI

```python
from navige import Navige
from navige.integrations.crewai import governed_tool

tl = Navige(api_key="tl_...", agent_name="crew-agent")

@governed_tool(tl)
class SendEmailTool(BaseTool):
    name = "send_email"
    description = "Send an email"

    def _run(self, to: str, subject: str, body: str) -> str:
        ...  # only runs if Navige allows it
```

## Governance rules

```python
# Create a rule in plain English
tl.create_rule(
    "Any wire transfer over £10,000 requires human approval",
    action="approve",
    approver_email="cfo@mycompany.com",
)

# Block a tool instantly (kill-switch)
tl.block_tool("drop_table", reason="Emergency: DB ops disabled")

# Unblock
tl.unblock_tool("drop_table")
```

## Audit log

```python
# Get recent calls
logs = tl.get_logs(limit=100, status="BLOCKED")

# Export as CSV
csv = tl.export_logs()

# Stats
stats = tl.get_stats()
print(stats["total"], stats["blocked"])
```

## Human approvals

```python
# List pending
pending = tl.get_pending_approvals()

# Approve or deny programmatically
tl.decide(pending[0]["id"], "approved")
```

## Context manager

```python
with Navige(api_key="tl_...") as tl:
    tl.intercept("my_tool", {...})
# connection closed automatically
```

## MCP (Claude Desktop)

```python
url = Navige.mcp_url("tl_your_key")
# → "https://api.navige.ai/sse?api_key=tl_..."
```

Paste this into your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "navige": { "url": "<paste url here>" }
  }
}
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `NAVIGE_API_KEY` | Your API key (avoids passing it in code) |
| `NAVIGE_AGENT_NAME` | Default agent name for all intercepts |
| `NAVIGE_BASE_URL` | Override API base URL (for on-prem deployments) |

## Links

- [Dashboard](https://app.navige.ai)
- [Docs](https://navige.ai/docs.html)
- [Sign up free](https://navige.ai/signup)
- [npm SDK](https://npmjs.com/package/navige)

## License

MIT
