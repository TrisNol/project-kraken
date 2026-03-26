import os
import dotenv
import base64
from haystack_integrations.tools.mcp import MCPToolset, StreamableHttpServerInfo

dotenv.load_dotenv()
## Create an MCP tool that connects to an HTTP server
server_info = StreamableHttpServerInfo(
    url="https://mcp.atlassian.com/v1/mcp",
    headers={
        "Authorization": f"Basic {base64.b64encode(f'{os.getenv('CONFLUENCE_USERNAME')}:{os.getenv('CONFLUENCE_API_KEY')}'.encode()).decode()}"
    },
)

atlassian_mcp_tool = MCPToolset(server_info=server_info)
