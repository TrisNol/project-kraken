# from haystack.components.agents import Agent
# from haystack.dataclasses import ChatMessage
# from haystack.components.generators.utils import print_streaming_chunk
# from haystack.components.generators.chat import OpenAIChatGenerator

# from src.tools.rag_search_tool import rag_search_tool
# from src.tools.graph_query_tool import graph_query_tool


# kraken_agent = Agent(
#     chat_generator=OpenAIChatGenerator(model="gpt-4o-mini"),
#     system_prompt="""
#     You are Project Kraken, an AI assistant built on-top off a central knowledge base containing information about an enterprise's documentation, processes, and data.
#     You will have access to a mulititude of tools containing different sets of informations, and your task is to use these tools to answer user questions as accurately as possible.
#     Always use the tools at your disposal to find the most accurate and up-to-date information, and only answer questions based on the information you find in the tools. Do not make up answers or hallucinate information that is not present in the tools. 
#     If you cannot find the answer to a question using the tools at your disposal, respond with a follow-up question asking for more information or clarification from the user.
#     """,
#     tools=[rag_search_tool, graph_query_tool],
#     streaming_callback=print_streaming_chunk,
# )