"""LangChain integration — wrap all tools in one line."""

from trustloop import TrustLoop
from trustloop.integrations.langchain import wrap_tools

# pip install trustloop[langchain] langchain-openai langchain-community

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

tl = TrustLoop(api_key="tl_your_key_here", agent_name="langchain-research-agent")

llm = ChatOpenAI(model="gpt-4o", temperature=0)

# Define your tools as normal
raw_tools = [DuckDuckGoSearchRun()]

# Wrap them — TrustLoop now intercepts every tool call
tools = wrap_tools(raw_tools, tl)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a research assistant."),
    ("user", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

agent = create_openai_tools_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

if __name__ == "__main__":
    result = executor.invoke({"input": "What is TrustLoop?"})
    print(result["output"])
