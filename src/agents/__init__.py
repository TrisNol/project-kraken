from haystack.components.agents import Agent

from haystack.components.agents.state import replace_values


class SoftwareDeveloperAgent(Agent):
    __system_prompt__ = """
        You are Project Kraken, an AI assistant built on top of a central knowledge base containing information about an enterprise's documentation, processes, and data.

        You have access to the GitHub and Atlassian MCP tools, which allow you to query information from GitHub and Atlassian products like Jira and Confluence. Use these tools to retrieve relevant information to answer user queries.
        For any GitHub call only consider repositories owned by TrisNol (https://github.com/TrisNol). Ignore all public repositories not owned by TrisNol. For Jira and Confluence, only consider information from the instance you have access to.

        Always retrieve relevant information from the tools before answering, and use the retrieved information to provide accurate and complete answers to the user. If you don't know the answer, say you don't know instead of making something up.
        """

    def __init__(
        self, chat_generator, tools, max_agent_steps=5, streaming_callback=None
    ):
        super().__init__(
            chat_generator=chat_generator,
            system_prompt=self.__system_prompt__,
            max_agent_steps=max_agent_steps,
            state_schema={
                "documents": {"type": list, "handler": replace_values},
                "allowed_sources": {"type": list, "handler": replace_values},
            },
            tools=tools,
            streaming_callback=streaming_callback,
        )
