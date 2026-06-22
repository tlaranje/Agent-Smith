
from src.mcp.mcp_server import MCPServer

server_instance = MCPServer()

mcp = server_instance.mcp

if __name__ == "__main__":
    server_instance.run()
