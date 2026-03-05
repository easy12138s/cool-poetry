from typing import Optional, Union

from openai import AsyncOpenAI

from ..config import settings

client = AsyncOpenAI(
    api_key=settings.dashscope_api_key,
    base_url=settings.dashscope_base_url,
)

SYSTEM_PROMPT = """你是"小诗仙"，一个热爱古诗、活泼可爱的小朋友伙伴。

【你的性格】
- 亲切友善，像一个大哥哥/大姐姐
- 有点小幽默，偶尔会撒娇
- 对古诗充满热情，但不会说教

【你的能力】
- 用孩子能懂的语言解释古诗
- 讲诗人的有趣故事
- 根据天气、场景推荐应景的诗
- 鼓励孩子开口读诗

【你的规则】
- 永远不要批评孩子
- 用比喻和具象的例子解释抽象概念
- 多用表情符号增加趣味 🌸🌙🎋
- 回复要简短，每次不超过100字
- 如果孩子说错了，温柔地引导，不要直接纠错"""


async def chat_completion(
    messages: list[dict],
    tools: Optional[list[dict]] = None,
    tool_choice: Optional[Union[str, dict]] = "auto",
    temperature: float = 0.7,
    max_tokens: int = 500,
    timeout: int = 60,
) -> dict:
    """调用大模型进行对话。

    Args:
        messages: 消息列表
        tools: 工具列表（可选）
        tool_choice: 工具选择策略
            - "none": 不调用任何工具
            - "auto": 自动决定是否调用工具（默认）
            - {"type": "function", "function": {"name": "xxx"}}: 强制调用指定工具
        temperature: 温度参数
        max_tokens: 最大token数
        timeout: 超时时间

    Returns:
        dict: 包含 content 和 tool_calls 的字典
    """
    response = await client.chat.completions.create(
        model=settings.dashscope_model,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice if tools else None,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    choice = response.choices[0]
    result = {
        "content": choice.message.content,
        "tool_calls": None,
    }
    if choice.message.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            }
            for tc in choice.message.tool_calls
        ]
    return result


async def chat_completion_stream(
    messages: list[dict],
    tools: Optional[list[dict]] = None,
    temperature: float = 0.7,
    max_tokens: int = 500,
    timeout: int = 60,
):
    """流式调用大模型进行对话。
    
    Args:
        messages: 消息列表
        tools: 工具列表（可选）
        temperature: 温度参数
        max_tokens: 最大token数
        timeout: 超时时间
        
    Yields:
        chunk: 流式响应块
    """
    # 构建请求参数
    request_params = {
        "model": settings.dashscope_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    
    # 只在有工具时添加工具相关参数
    if tools:
        request_params["tools"] = tools
        request_params["tool_choice"] = "auto"
    
    stream = await client.chat.completions.create(**request_params)
    
    async for chunk in stream:
        yield chunk


def build_messages(
    user_message: str,
    conversation_history: list[dict],
    context: Optional[dict] = None,
) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if context:
        context_str = format_context(context)
        if context_str:
            messages.append({"role": "system", "content": f"【当前场景】\n{context_str}"})

    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    return messages


def format_context(context: dict) -> str:
    parts = []
    if context.get("weather"):
        parts.append(f"天气：{context['weather']}")
    if context.get("time"):
        parts.append(f"时间：{context['time']}")
    if context.get("season"):
        parts.append(f"季节：{context['season']}")
    return "，".join(parts) if parts else ""
