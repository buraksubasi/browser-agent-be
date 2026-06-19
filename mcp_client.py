# backend/mcp_client.py
import sys
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPClient:
    def __init__(self):
        self.session = None
        self._ctx = None

    async def connect(self):
        params = StdioServerParameters(
            command=sys.executable,  # "python" yerine aktif venv'deki Python
            args=[os.path.join(os.path.dirname(__file__), "mcp_server.py")]  # tam path
        )
        self._ctx = stdio_client(params)
        read, write = await self._ctx.__aenter__()
        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        await self.session.initialize()

    async def call_tool(self, name: str, arguments: dict) -> str:
        result = await self.session.call_tool(name, arguments)
        return result.content[0].text

    async def disconnect(self):
        if self.session:
            await self.session.__aexit__(None, None, None)
        if self._ctx:
            await self._ctx.__aexit__(None, None, None)