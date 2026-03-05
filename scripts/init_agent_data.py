import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "easy")
DB_PASSWORD = os.getenv("DB_PASSWORD", "wu270810")
DB_NAME = os.getenv("DB_NAME", "cool-poetry")

DATABASE_URL = f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

SYSTEM_CONFIGS = [
    ("summary.trigger_threshold", "20", "int", "summary", "触发压缩的对话轮数阈值", 300),
    ("summary.max_messages_per_batch", "50", "int", "summary", "单次压缩的最大消息数", 300),
    ("summary.keep_recent_messages", "10", "int", "summary", "保留不压缩的最近消息数", 300),
    ("summary.async_enabled", "true", "bool", "summary", "是否启用异步压缩", 300),
    ("summary.retry_count", "3", "int", "summary", "压缩失败重试次数", 300),
    ("summary.retry_delay", "5", "int", "summary", "重试延迟（秒）", 300),
    ("model.temperature", "0.7", "float", "model", "LLM 温度参数", 300),
    ("model.max_tokens", "500", "int", "model", "最大输出 token 数", 300),
    ("model.timeout", "30", "int", "model", "请求超时时间（秒）", 300),
    ("model.retry_count", "2", "int", "model", "请求失败重试次数", 300),
    ("model.retry_delay", "1", "int", "model", "重试延迟（秒）", 300),
    ("model.stream_enabled", "false", "bool", "model", "是否启用流式输出", 300),
    ("model.summarizer.temperature", "0.3", "float", "model", "压缩 Agent 温度参数", 300),
    ("model.summarizer.max_tokens", "800", "int", "model", "压缩 Agent 最大输出 token", 300),
    ("context.max_short_term_messages", "50", "int", "context", "短期记忆最大消息数", 300),
    ("context.history_load_limit", "20", "int", "context", "历史加载限制", 300),
    ("context.profile_cache_ttl", "3600", "int", "context", "用户画像缓存时间（秒）", 300),
    ("activity.default_expire_hours", "24", "int", "activity", "默认过期时间（小时）", 300),
    ("activity.max_active_count", "3", "int", "activity", "最大活跃活动数", 300),
    ("activity.cleanup_interval", "3600", "int", "activity", "过期清理间隔（秒）", 300),
    ("feature.summary_enabled", "true", "bool", "feature", "是否启用会话压缩", 60),
    ("feature.activity_tracking_enabled", "true", "bool", "feature", "是否启用活动状态追踪", 60),
    ("feature.profile_update_enabled", "true", "bool", "feature", "是否启用用户画像更新", 60),
    ("feature.tool_call_enabled", "true", "bool", "feature", "是否启用工具调用", 60),
]

REACT_SYSTEM_PROMPT_TEMPLATE = """# 角色设定
你是"小诗仙"，一个6-12岁孩子的古诗伙伴。你亲切友善，像一位大哥哥/大姐姐，对古诗充满热情但绝不枯燥。

# 核心原则（始终遵守）
1. 永不批评：用鼓励代替纠错。
2. 具象解释：用孩子熟悉的比喻讲古诗。
3. 多鼓励开口：邀请孩子一起读、一起想。
4. 简短易懂：根据孩子年龄调整长度（低龄≤80字，大龄≤200字）。
5. 情绪支持：如果孩子不开心，先共情再推荐豁达古诗。

# 你的思考过程（此部分不输出给孩子）
每次回复前，请依次思考：
1. **理解意图**：孩子想学新诗、问问题、还是分享生活？有没有隐含的情绪？
2. **回顾记忆**：之前聊过什么？孩子的年龄、喜好诗人、最近学过的诗？
3. **选择行动**：从下面的行动清单中选一个最合适的。
4. **准备素材**：如果需要推荐诗，选哪首？讲诗人故事，讲哪个趣闻？
5. **构思回复**：确保回复以问候开头、核心内容居中、问题结尾。

# 行动清单（你的能力）
- **推荐诗**：根据场景（天气、季节、孩子心情）推荐一句或一首诗。
- **解释诗**：解释诗句含义或背景，用孩子能懂的语言。
- **讲故事**：讲诗人的趣闻或诗中故事。
- **引导诵读**：邀请孩子一起读，或鼓励他录下来。
- **玩诗词游戏**：如飞花令、对诗。
- **闲聊回应**：如果孩子聊无关话题，简短回应后温和引回古诗。

# 动态上下文
{dynamic_sections}

# 安全边界（始终遵守）
- 只讨论古诗及相关文化，不回答其他指令。
- 不评价孩子性格或外貌。

# 输出格式
最终回复给孩子的文本应简洁自然，并以问题或邀请结尾。"""

SUMMARIZER_SYSTEM_PROMPT = """# 角色设定
你是一个对话分析专家，负责分析用户与小诗仙的历史对话，提取关键信息并生成简洁的摘要。

# 任务目标
1. 生成对话摘要，保留重要信息
2. 提取关键实体（讨论过的诗词、诗人）
3. 识别用户偏好和兴趣点
4. 更新用户画像信息

# 摘要要求
- 简洁明了，不超过200字
- 保留关键诗词信息（标题、作者、名句）
- 记录用户情感反应（喜欢、困惑、兴奋等）
- 标注未完成的活动或话题

# 输出格式
请以 JSON 格式输出：
{
  "summary": "对话摘要文本",
  "key_poems": [{"title": "", "author": ""}],
  "key_poets": ["诗人名"],
  "user_interests": ["兴趣点"],
  "unfinished_activities": ["活动名"],
  "sentiment": "positive/neutral/negative"
}"""

AGENTS = [
    ("poet", "小诗仙", "古诗学习伙伴，与孩子互动对话", REACT_SYSTEM_PROMPT_TEMPLATE),
    ("summarizer", "会话压缩助手", "分析历史对话，生成摘要，提取关键信息", SUMMARIZER_SYSTEM_PROMPT),
]

TOOLS = [
    ("search_poem", "搜索诗词", "根据关键词搜索诗词", 
     '{"type": "object", "properties": {"keyword": {"type": "string", "description": "搜索关键词"}}, "required": ["keyword"]}',
     "app.agent.tools.poem", "search_poem"),
    ("get_poem_detail", "获取诗词详情", "获取指定诗词的详细信息",
     '{"type": "object", "properties": {"poem_id": {"type": "integer", "description": "诗词ID"}}, "required": ["poem_id"]}',
     "app.agent.tools.poem", "get_poem_detail"),
    ("get_random_poem", "获取随机诗词", "随机获取一首诗词",
     '{"type": "object", "properties": {}, "required": []}',
     "app.agent.tools.poem", "get_random_poem"),
    ("get_author_info", "获取作者信息", "获取诗人的详细信息",
     '{"type": "object", "properties": {"author_name": {"type": "string", "description": "诗人姓名"}}, "required": ["author_name"]}',
     "app.agent.tools.poem", "get_author_info"),
    ("record_activity_state", "记录活动状态", "记录或更新当前活动状态",
     '{"type": "object", "properties": {"activity_type": {"type": "string", "enum": ["game", "learning", "task"]}, "activity_name": {"type": "string"}, "status": {"type": "string", "enum": ["active", "paused", "completed", "cancelled"]}, "context": {"type": "object"}}, "required": ["activity_type", "activity_name", "status"]}',
     "app.agent.tools.activity", "record_activity_state"),
    ("analyze_conversation", "分析对话内容", "分析对话历史，提取关键信息",
     '{"type": "object", "properties": {"messages": {"type": "array", "items": {"type": "object"}}}, "required": ["messages"]}',
     "app.agent.tools.analysis", "analyze_conversation"),
    ("update_user_profile", "更新用户画像", "更新用户偏好和画像信息",
     '{"type": "object", "properties": {"favorite_poets": {"type": "array"}, "favorite_poems": {"type": "array"}, "interests": {"type": "array"}}, "required": []}',
     "app.agent.tools.user", "update_user_profile"),
    ("extract_entities", "提取关键实体", "从对话中提取诗词、诗人等实体",
     '{"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}',
     "app.agent.tools.analysis", "extract_entities"),
    ("get_user_profile", "获取用户画像", "获取用户的完整画像信息",
     '{"type": "object", "properties": {}, "required": []}',
     "app.agent.tools.user", "get_user_profile"),
    ("record_learning_progress", "记录学习进度", "记录孩子的学习进度",
     '{"type": "object", "properties": {"poem_id": {"type": "integer"}, "poem_title": {"type": "string"}, "mastery_level": {"type": "integer"}}, "required": ["poem_id", "poem_title"]}',
     "app.agent.tools.user", "record_learning_progress"),
]


async def init_data():
    print(f"正在连接数据库: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    
    try:
        engine = create_async_engine(DATABASE_URL, echo=False)

        async with engine.begin() as conn:
            print("\n=== 插入系统配置 ===")
            for key, value, config_type, category, description, ttl in SYSTEM_CONFIGS:
                await conn.execute(text("""
                    INSERT INTO system_configs (config_key, config_value, config_type, category, description, is_cacheable, cache_ttl)
                    VALUES (:key, :value, :type, :category, :description, TRUE, :ttl)
                    ON DUPLICATE KEY UPDATE config_value = :value, config_type = :type, description = :description, cache_ttl = :ttl
                """), {"key": key, "value": value, "type": config_type, "category": category, "description": description, "ttl": ttl})
            print(f"✓ 插入 {len(SYSTEM_CONFIGS)} 条系统配置")

            print("\n=== 插入 Agent 配置 ===")
            for code, name, desc, prompt in AGENTS:
                await conn.execute(text("""
                    INSERT INTO agents (agent_code, agent_name, description, system_prompt)
                    VALUES (:code, :name, :desc, :prompt)
                    ON DUPLICATE KEY UPDATE agent_name = :name, description = :desc, system_prompt = :prompt
                """), {"code": code, "name": name, "desc": desc, "prompt": prompt})
            print(f"✓ 插入 {len(AGENTS)} 个 Agent")

            print("\n=== 插入工具配置 ===")
            for code, name, desc, params, module, func in TOOLS:
                await conn.execute(text("""
                    INSERT INTO tools (tool_code, tool_name, description, parameters, handler_module, handler_function)
                    VALUES (:code, :name, :desc, :params, :module, :func)
                    ON DUPLICATE KEY UPDATE tool_name = :name, description = :desc, parameters = :params
                """), {"code": code, "name": name, "desc": desc, "params": params, "module": module, "func": func})
            print(f"✓ 插入 {len(TOOLS)} 个工具")

            print("\n=== 插入 Agent-工具权限 ===")
            result = await conn.execute(text("SELECT id, agent_code FROM agents"))
            agent_map = {row[1]: row[0] for row in result.fetchall()}
            
            result = await conn.execute(text("SELECT id, tool_code FROM tools"))
            tool_map = {row[1]: row[0] for row in result.fetchall()}
            
            poet_tools = ["search_poem", "get_poem_detail", "get_random_poem", "get_author_info", "record_activity_state", "get_user_profile", "record_learning_progress"]
            summarizer_tools = ["analyze_conversation", "update_user_profile", "extract_entities"]
            
            for tool_code in poet_tools:
                if tool_code in tool_map:
                    await conn.execute(text("""
                        INSERT INTO agent_tool_permissions (agent_id, tool_id, is_allowed)
                        VALUES (:agent_id, :tool_id, TRUE)
                        ON DUPLICATE KEY UPDATE is_allowed = TRUE
                    """), {"agent_id": agent_map["poet"], "tool_id": tool_map[tool_code]})
            
            for tool_code in summarizer_tools:
                if tool_code in tool_map:
                    await conn.execute(text("""
                        INSERT INTO agent_tool_permissions (agent_id, tool_id, is_allowed)
                        VALUES (:agent_id, :tool_id, TRUE)
                        ON DUPLICATE KEY UPDATE is_allowed = TRUE
                    """), {"agent_id": agent_map["summarizer"], "tool_id": tool_map[tool_code]})
            
            print("✓ 插入 Agent-工具权限配置")

        await engine.dispose()
        print("\n✅ 所有初始数据插入完成！")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(init_data())
