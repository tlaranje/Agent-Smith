from mcp.server.fastmcp import FastMCP
import sqlite3

DB_PATH = "./community.db"


class MCPServer:
    def __init__(self) -> None:
        self.mcp = FastMCP("Community Chatters")

        @self.mcp.tool(name="get_top_chatters")
        def get_top_chatters(limit: int = 10) -> list[dict]:
            """Return chatters ranked by message count."""
            return self._get_top_chatters_db(limit)

    def _get_top_chatters_db(self, limit: int = 10) -> list[dict]:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, messages FROM chatters "
            "ORDER BY messages DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"name": name, "messages": messages} for name, messages in rows
        ]
