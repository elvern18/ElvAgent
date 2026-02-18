"""
Database MCP Server for ElvAgent.
Provides Claude with database query capabilities through MCP tools.
"""

import asyncio
from datetime import date
from pathlib import Path
from typing import Any

import mcp.server.stdio
from mcp.server import Server
from mcp.types import TextContent, Tool

from src.config.settings import settings
from src.core.state_manager import StateManager
from src.utils.logger import get_logger

logger = get_logger("mcp.database")


class DatabaseServer:
    """MCP server providing database tools for Claude."""

    def __init__(self, db_path: Path | None = None):
        """
        Initialize Database MCP Server.

        Args:
            db_path: Path to SQLite database (defaults to settings.database_path)
        """
        self.db_path = db_path or settings.database_path
        self.state_manager = StateManager(db_path=self.db_path)
        self.server = Server("database-server")

        # Register tools
        self._register_tools()

        logger.info("database_mcp_server_initialized", db_path=str(self.db_path))

    def _register_tools(self):
        """Register all MCP tools."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available database tools."""
            return [
                Tool(
                    name="check_duplicate",
                    description="Check if content already exists in the database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "Content URL to check"},
                            "title": {"type": "string", "description": "Content title to check"},
                        },
                        "required": ["url", "title"],
                    },
                ),
                Tool(
                    name="store_content",
                    description="Store a published content item in the database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "Content URL"},
                            "title": {"type": "string", "description": "Content title"},
                            "source": {
                                "type": "string",
                                "description": "Content source (arxiv, huggingface, etc.)",
                            },
                            "category": {
                                "type": "string",
                                "description": "Content category (research, product, funding, news)",
                            },
                            "newsletter_date": {
                                "type": "string",
                                "description": "Newsletter date (YYYY-MM-DD-HH)",
                            },
                            "metadata": {"type": "object", "description": "Additional metadata"},
                        },
                        "required": ["url", "title", "source"],
                    },
                ),
                Tool(
                    name="get_metrics",
                    description="Retrieve API usage metrics for a specific date",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "date": {
                                "type": "string",
                                "description": "Date in YYYY-MM-DD format (defaults to today)",
                            }
                        },
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool execution."""
            logger.debug("tool_called", tool_name=name, arguments=arguments)

            try:
                if name == "check_duplicate":
                    result = await self._check_duplicate(
                        url=arguments["url"], title=arguments["title"]
                    )
                elif name == "store_content":
                    result = await self._store_content(item=arguments)
                elif name == "get_metrics":
                    result = await self._get_metrics(target_date=arguments.get("date"))
                else:
                    raise ValueError(f"Unknown tool: {name}")

                logger.info("tool_executed", tool_name=name, success=True)
                return [TextContent(type="text", text=str(result))]

            except Exception as e:
                logger.error(
                    "tool_execution_failed",
                    tool_name=name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def _check_duplicate(self, url: str, title: str) -> dict[str, Any]:
        """
        Check if content already exists in database.

        Args:
            url: Content URL
            title: Content title

        Returns:
            Dictionary with is_duplicate, content_id, and optionally first_seen
        """
        # Generate content ID
        content_id = self.state_manager.generate_content_id(url, title)

        # Check if duplicate
        is_duplicate = await self.state_manager.check_duplicate(url, title)

        result = {"is_duplicate": is_duplicate, "content_id": content_id}

        # If duplicate, get first_seen timestamp
        if is_duplicate:
            import aiosqlite

            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT first_seen FROM content_fingerprints WHERE content_hash = ?",
                    (content_id,),
                )
                row = await cursor.fetchone()
                if row:
                    result["first_seen"] = row[0]

        logger.debug("duplicate_check_completed", content_id=content_id, is_duplicate=is_duplicate)

        return result

    async def _store_content(self, item: dict[str, Any]) -> dict[str, Any]:
        """
        Store content item in database.

        Args:
            item: Content item dictionary

        Returns:
            Dictionary with success, row_id, and content_id
        """
        try:
            # Validate required fields
            required_fields = ["url", "title", "source"]
            for field in required_fields:
                if field not in item:
                    raise ValueError(f"Missing required field: {field}")

            # Store content
            row_id = await self.state_manager.store_content(item)

            # Generate content ID
            content_id = self.state_manager.generate_content_id(item["url"], item["title"])

            result = {"success": True, "row_id": row_id, "content_id": content_id}

            logger.info("content_stored", row_id=row_id, content_id=content_id)

            return result

        except Exception as e:
            logger.error("content_store_failed", error=str(e), error_type=type(e).__name__)
            return {"success": False, "error": str(e)}

    async def _get_metrics(self, target_date: str | None = None) -> dict[str, Any]:
        """
        Get API usage metrics for a specific date.

        Args:
            target_date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            Dictionary with metrics and total_cost
        """
        # Default to today if not specified
        if target_date is None:
            target_date = str(date.today())

        # Get metrics from state manager
        metrics = await self.state_manager.get_metrics(target_date)

        # Format result
        result = {
            "date": target_date,
            "metrics": {k: v for k, v in metrics.items() if k != "total_cost"},
            "total_cost": metrics.get("total_cost", 0.0),
        }

        logger.debug("metrics_retrieved", date=target_date, total_cost=result["total_cost"])

        return result

    async def run(self):
        """Run the MCP server with stdio transport."""
        logger.info("database_mcp_server_starting")

        # Initialize database
        await self.state_manager.init_db()

        # Run server
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, write_stream, self.server.create_initialization_options()
            )


async def main():
    """Main entry point for running the database MCP server."""
    server = DatabaseServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
