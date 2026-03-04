from typing import Any, Callable


class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        execute: Callable,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.execute = execute

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    _tools: dict[str, Tool] = {}

    @classmethod
    def register(cls, tool: Tool):
        cls._tools[tool.name] = tool

    @classmethod
    def get(cls, name: str) -> Tool | None:
        return cls._tools.get(name)

    @classmethod
    def get_all_tools(cls) -> list[dict]:
        return [tool.to_openai_tool() for tool in cls._tools.values()]

    @classmethod
    def get_tools_by_codes(cls, tool_codes: list[str]) -> list[dict]:
        tools = []
        for code in tool_codes:
            tool = cls._tools.get(code)
            if tool:
                tools.append(tool.to_openai_tool())
        return tools

    @classmethod
    def clear(cls):
        cls._tools = {}


def tool(name: str, description: str, parameters: dict):
    def decorator(func: Callable):
        t = Tool(name, description, parameters, func)
        ToolRegistry.register(t)
        return func

    return decorator
