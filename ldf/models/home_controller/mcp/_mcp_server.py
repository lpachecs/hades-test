"""
MCP Server supporting both stdio and SSE transports
"""
import asyncio
import inspect
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server import Server
from mcp.types import TextContent, Tool

from ldf.models.home_controller import HomeController
from ldf.models.home_controller.mcp._tools.get_system_endpoints import \
    GetDevicesTool
from ldf.models.home_controller.mcp._tools.get_system_routes import \
    GetRoutesTool

NATS_SERVERS = ['10.1.215.71']


@dataclass
class HocContext:
    """Provide typesafe access to initialised HomeController"""
    hoc: HomeController


@asynccontextmanager
async def hoc_context(server: Server) -> AsyncIterator[HocContext]:
    """Create and manage HomeController context"""
    hoc = await HomeController.create(home_addrs=NATS_SERVERS)
    try:
        yield HocContext(hoc=hoc)
    finally:
        await hoc.close()


# Create MCP server instance
mcp_server = Server(name="LDF MCP", lifespan=hoc_context)

tool_instances = {
    "get_devices": GetDevicesTool(),
    "get_routes": GetRoutesTool(),
}


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """Return list of available tools"""

    return [
        tool.to_mcp_tool() for tool in tool_instances.values()
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a tool by name"""

    hoc = mcp_server.request_context.lifespan_context.hoc
    tool = tool_instances.get(name, None)
    if not tool:
        raise ValueError(f"Unknown tool: {name}")

    # Handle both sync and async tools
    result = tool.execute(hoc, **arguments)
    if inspect.iscoroutine(result):
        result = await result
    return result


async def run_stdio():
    """Run with stdio transport (for Claude Desktop direct launch)"""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options()
        )


async def run_sse():
    """Run with SSE transport (for HTTP connections)"""
    import json

    import uvicorn
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.routing import Route

    # Create SSE transport
    sse = SseServerTransport("/messages")

    async def handle_sse(request: Request) -> Response:
        """Handle SSE connection endpoint"""
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send
        ) as streams:
            await mcp_server.run(
                streams[0],
                streams[1],
                mcp_server.create_initialization_options()
            )
        return Response()

    async def handle_messages(request: Request) -> Response:
        """Handle client-to-server messages endpoint"""
        await sse.handle_post_message(request.scope, request.receive, request._send)
        return Response()

    async def health_check(request: Request) -> Response:
        """Health check endpoint for monitoring"""
        return Response(
            content=json.dumps({
                "status": "healthy",
                "server": "LDF",
                "tools": [tool for tool in mcp_server.list_tools()]
            }),
            media_type="application/json"
        )

    # Create Starlette application
    app = Starlette(
        debug=True,
        routes=[
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
            Route("/health", endpoint=health_check, methods=["GET"]),
        ]
    )

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """
    Main entry point - detects transport type based on environment

    stdio mode: When launched by Claude Desktop directly
    SSE mode: When run as HTTP server (--sse flag or default)
    """

    # Check if running in stdio mode (launched by Claude Desktop)
    # Claude Desktop doesn't set terminal attributes, so we check if stdin is a TTY
    if "--stdio" in sys.argv or not sys.stdin.isatty():
        print("Starting in stdio mode...", file=sys.stderr)
        await run_stdio()
    else:
        # Default to SSE mode for HTTP server
        print("Starting in SSE mode on http://0.0.0.0:8000", file=sys.stderr)
        await run_sse()


if __name__ == "__main__":
    asyncio.run(main())
