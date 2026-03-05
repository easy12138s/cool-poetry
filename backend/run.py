import asyncio
import signal
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

env_file = backend_dir.parent / ".env"
load_dotenv(env_file)

import uvicorn


def handle_signal(sig, frame):
    """处理 Ctrl+C 信号，优雅关闭"""
    print("\n收到关闭信号，正在优雅关闭服务...")
    # 给事件循环一点时间处理未完成的任务
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.stop()
    sys.exit(0)


if __name__ == "__main__":
    # 注册信号处理器
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Windows 平台特殊处理
    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, handle_signal)
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # 配置优雅关闭
        lifespan="on",
        timeout_keep_alive=5,
    )
