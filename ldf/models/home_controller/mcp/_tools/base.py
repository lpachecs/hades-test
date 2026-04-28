from abc import ABC, abstractmethod
from typing import Any

from mcp.types import Tool


class BaseTool(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description"""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> dict:
        """JSON schema for tool inputs"""
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    @abstractmethod
    def execute(self, hoc, arguments: Any = None) -> Any:
        """Execute the tool logic"""
        pass

    def to_mcp_tool(self) -> Tool:
        """Convert to MCP Tool format"""
        return Tool(
            name=self.name,
            description=self.description,
            inputSchema=self.input_schema
        )

    def to_requests_tool(self) -> dict[str, Any]:
        """Convert to Requests Tool format"""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema.get("properties", {}),
            "required": self.input_schema.get("required", [])
        }
