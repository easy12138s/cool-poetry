import json
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.base import ToolRegistry
from app.services.llm import chat_completion


async def execute_tool_call(
    db: AsyncSession,
    tool_name: str,
    arguments: str,
) -> str:
    tool = ToolRegistry.get(tool_name)
    if not tool:
        return f"未知的工具：{tool_name}"

    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
        result = await tool.execute(db=db, **args)
        return result
    except Exception as e:
        return f"工具执行错误：{str(e)}"


async def run_agent(
    db: AsyncSession,
    messages: list[dict],
    max_tool_calls: int = 3,
) -> tuple[str, Optional[dict]]:
    tools = ToolRegistry.get_all_tools()

    if not tools:
        response = await chat_completion(messages)
        return response["content"], None

    response = await chat_completion(messages, tools=tools)
    content = response["content"]
    tool_calls = response["tool_calls"]

    call_count = 0
    poem_data = None

    while tool_calls and call_count < max_tool_calls:
        call_count += 1

        for tc in tool_calls:
            tool_name = tc["name"]
            arguments = tc["arguments"]

            tool_result = await execute_tool_call(db, tool_name, arguments)

            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                }]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_result
            })

            if tool_name in ["search_poem", "get_poem_detail", "get_random_poem"]:
                poem_data = {
                    "tool": tool_name,
                    "arguments": json.loads(arguments) if isinstance(arguments, str) else arguments,
                    "result": tool_result,
                }

        response = await chat_completion(messages, tools=tools)
        content = response["content"]
        tool_calls = response["tool_calls"]

    return content, poem_data
