import os
import dotenv
from haystack_integrations.tools.mcp import MCPToolset, StreamableHttpServerInfo


dotenv.load_dotenv()
## Create an MCP tool that connects to an HTTP server
server_info = StreamableHttpServerInfo(
    url="https://api.githubcopilot.com/mcp/",
    headers={
        "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
        "X-MCP-Toolsets": "repos,issues",
        "X-MCP-Readonly": "true",
    },
)

github_mcp_tool = MCPToolset(server_info=server_info)
