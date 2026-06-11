"""CrewAI integration — govern all crew tools."""

# pip install trustloop[crewai] crewai

from crewai import Agent, Task, Crew
from crewai.tools import BaseTool
from trustloop import TrustLoop
from trustloop.integrations.crewai import governed_tool, wrap_crew_tools

tl = TrustLoop(api_key="tl_your_key_here", agent_name="crewai-outreach-agent")


# ── Option A: decorate individual tool classes ────────────────────────────────

@governed_tool(tl)
class SendEmailTool(BaseTool):
    name: str = "send_email"
    description: str = "Send an email. Args: to (str), subject (str), body (str)"

    def _run(self, to: str, subject: str, body: str) -> str:
        # Only runs if TrustLoop allows it
        print(f"Email sent to {to}")
        return f"Email sent to {to}"


@governed_tool(tl)
class DatabaseQueryTool(BaseTool):
    name: str = "query_database"
    description: str = "Run a SQL query. Args: query (str)"

    def _run(self, query: str) -> str:
        print(f"Running query: {query}")
        return "Results: ..."


# ── Option B: wrap existing tool instances ────────────────────────────────────
# tools = wrap_crew_tools([existing_tool_1, existing_tool_2], tl)


researcher = Agent(
    role="Researcher",
    goal="Find and summarise relevant information",
    backstory="Expert researcher with access to databases and email",
    tools=[SendEmailTool(), DatabaseQueryTool()],
    verbose=True,
)

task = Task(
    description="Research TrustLoop and send a summary to ceo@example.com",
    expected_output="Confirmation of email sent",
    agent=researcher,
)

crew = Crew(agents=[researcher], tasks=[task], verbose=True)

if __name__ == "__main__":
    result = crew.kickoff()
    print(result)
