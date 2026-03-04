# 此文件保留用于兼容性，Tool 相关类已移动到 tools/base.py
# 请从 .tools 导入 Tool, ToolRegistry, tool

from .tools import Tool, ToolRegistry, tool

__all__ = ["Tool", "ToolRegistry", "tool"]
