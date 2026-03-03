import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = "mysql+aiomysql://easy:wu270810@localhost:3306/cool-poetry"


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
    role ENUM('user', 'assistant') NOT NULL,
    content TEXT NOT NULL,
    audio_url VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (device_id) REFERENCES devices(id),
    FOREIGN KEY (poem_id) REFERENCES poems(id)
);
"""


async def init_tables():
    engine = create_async_engine(DATABASE_URL, echo=True)

    async with engine.begin() as conn:
        await conn.execute(text(CREATE_DEVICES_TABLE))
        print("✓ devices 表创建成功")

        await conn.execute(text(CREATE_USERS_TABLE))
        print("✓ users 表创建成功")

        await conn.execute(text(CREATE_CONVERSATIONS_TABLE))
        print("✓ conversations 表创建成功")

    await engine.dispose()
    print("\n所有业务表初始化完成！")


if __name__ == "__main__":
    asyncio.run(init_tables())
