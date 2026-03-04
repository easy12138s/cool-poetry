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


CREATE_DEVICES_TABLE = """
CREATE TABLE IF NOT EXISTS devices (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100),
    device_type ENUM('raspberry_pi', 'mini_program', 'web') DEFAULT 'raspberry_pi',
    status ENUM('online', 'offline', 'sleeping') DEFAULT 'offline',
    last_seen_at DATETIME,
    config JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
"""

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    device_id VARCHAR(36),
    nickname VARCHAR(50),
    age INT,
    avatar VARCHAR(255),
    settings JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active_at DATETIME,
    FOREIGN KEY (device_id) REFERENCES devices(id)
);
"""

CREATE_CONVERSATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS conversations (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36),
    device_id VARCHAR(36),
    poem_id INT,
    role ENUM('user', 'assistant', 'tool') NOT NULL,
    content TEXT NOT NULL,
    tool_calls JSON,
    tool_call_id VARCHAR(64),
    audio_url VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (device_id) REFERENCES devices(id),
    FOREIGN KEY (poem_id) REFERENCES poems(id)
);
"""

CREATE_USER_PROFILES_TABLE = """
CREATE TABLE IF NOT EXISTS user_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(36) UNIQUE NOT NULL,
    nickname VARCHAR(50),
    age INT,
    favorite_poets JSON,
    favorite_poems JSON,
    learning_progress JSON,
    preferences JSON,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

CREATE_SYSTEM_CONFIGS_TABLE = """
CREATE TABLE IF NOT EXISTS system_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    config_type ENUM('string', 'int', 'float', 'bool', 'json') DEFAULT 'string',
    category VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    is_cacheable BOOLEAN DEFAULT TRUE,
    cache_ttl INT DEFAULT 300,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_cacheable (is_cacheable, cache_ttl)
);
"""

CREATE_AGENTS_TABLE = """
CREATE TABLE IF NOT EXISTS agents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agent_code VARCHAR(50) UNIQUE NOT NULL,
    agent_name VARCHAR(100) NOT NULL,
    description TEXT,
    system_prompt TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    config JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
"""

CREATE_TOOLS_TABLE = """
CREATE TABLE IF NOT EXISTS tools (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tool_code VARCHAR(50) UNIQUE NOT NULL,
    tool_name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    parameters JSON NOT NULL,
    handler_module VARCHAR(255),
    handler_function VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    requires_db BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
"""

CREATE_AGENT_TOOL_PERMISSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS agent_tool_permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agent_id INT NOT NULL,
    tool_id INT NOT NULL,
    is_allowed BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_agent_tool (agent_id, tool_id),
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (tool_id) REFERENCES tools(id)
);
"""

CREATE_CONVERSATION_SUMMARIES_TABLE = """
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    session_id VARCHAR(36),
    summary_text TEXT NOT NULL,
    start_message_id VARCHAR(36),
    end_message_id VARCHAR(36),
    start_created_at DATETIME,
    end_created_at DATETIME,
    message_count INT DEFAULT 0,
    token_saved INT DEFAULT 0,
    key_entities JSON,
    sentiment VARCHAR(20),
    topics JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_created (user_id, created_at DESC),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

CREATE_ACTIVITY_STATES_TABLE = """
CREATE TABLE IF NOT EXISTS activity_states (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    activity_type VARCHAR(50) NOT NULL,
    activity_name VARCHAR(100),
    status ENUM('active', 'paused', 'completed', 'cancelled', 'expired') DEFAULT 'active',
    context JSON,
    priority INT DEFAULT 0,
    expires_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_status (user_id, status),
    INDEX idx_user_expires (user_id, expires_at),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""

ALTER_CONVERSATIONS_ADD_TOOL_CALLS = """
ALTER TABLE conversations ADD COLUMN tool_calls JSON;
"""

ALTER_CONVERSATIONS_ADD_TOOL_CALL_ID = """
ALTER TABLE conversations ADD COLUMN tool_call_id VARCHAR(64);
"""

ALTER_CONVERSATIONS_MODIFY_ROLE = """
ALTER TABLE conversations MODIFY COLUMN role ENUM('user', 'assistant', 'tool') NOT NULL;
"""


async def init_tables():
    print(f"正在连接数据库: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"用户名: {DB_USER}")
    
    try:
        engine = create_async_engine(DATABASE_URL, echo=False)

        async with engine.begin() as conn:
            print("\n=== 创建基础表 ===")
            await conn.execute(text(CREATE_DEVICES_TABLE))
            print("✓ devices 表创建成功")

            await conn.execute(text(CREATE_USERS_TABLE))
            print("✓ users 表创建成功")

            await conn.execute(text(CREATE_CONVERSATIONS_TABLE))
            print("✓ conversations 表创建成功")

            await conn.execute(text(CREATE_USER_PROFILES_TABLE))
            print("✓ user_profiles 表创建成功")

            print("\n=== 创建系统配置表 ===")
            await conn.execute(text(CREATE_SYSTEM_CONFIGS_TABLE))
            print("✓ system_configs 表创建成功")

            print("\n=== 创建 Agent 相关表 ===")
            await conn.execute(text(CREATE_AGENTS_TABLE))
            print("✓ agents 表创建成功")

            await conn.execute(text(CREATE_TOOLS_TABLE))
            print("✓ tools 表创建成功")

            await conn.execute(text(CREATE_AGENT_TOOL_PERMISSIONS_TABLE))
            print("✓ agent_tool_permissions 表创建成功")

            print("\n=== 创建会话压缩相关表 ===")
            await conn.execute(text(CREATE_CONVERSATION_SUMMARIES_TABLE))
            print("✓ conversation_summaries 表创建成功")

            print("\n=== 创建活动状态表 ===")
            await conn.execute(text(CREATE_ACTIVITY_STATES_TABLE))
            print("✓ activity_states 表创建成功")

            print("\n=== 更新 conversations 表结构 ===")
            try:
                await conn.execute(text(ALTER_CONVERSATIONS_ADD_TOOL_CALLS))
                print("✓ conversations.tool_calls 字段添加成功")
            except Exception as e:
                if "Duplicate column" in str(e):
                    print("✓ conversations.tool_calls 字段已存在")
                else:
                    print(f"⚠ tool_calls 字段处理: {e}")

            try:
                await conn.execute(text(ALTER_CONVERSATIONS_ADD_TOOL_CALL_ID))
                print("✓ conversations.tool_call_id 字段添加成功")
            except Exception as e:
                if "Duplicate column" in str(e):
                    print("✓ conversations.tool_call_id 字段已存在")
                else:
                    print(f"⚠ tool_call_id 字段处理: {e}")

            try:
                await conn.execute(text(ALTER_CONVERSATIONS_MODIFY_ROLE))
                print("✓ conversations.role 字段更新成功")
            except Exception as e:
                print(f"⚠ role 字段处理: {e}")

        await engine.dispose()
        print("\n✅ 所有业务表初始化完成！")
        print("\n请运行 init_agent_data.py 插入初始数据")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("\n请检查:")
        print("1. MySQL 是否已启动")
        print("2. 数据库用户名和密码是否正确")
        print("3. 数据库是否存在")
        raise


if __name__ == "__main__":
    asyncio.run(init_tables())
