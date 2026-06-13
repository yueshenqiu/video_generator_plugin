"""组件模块

新版 SDK 中组件通过 Mixin 模式合并到插件主类：
- VideoToolMixin: Tool 组件业务逻辑
- VideoCommandMixin: Command 组件业务逻辑

装饰器声明在 plugin.py 主类上，Mixin 提供实际实现。
"""

from .tool_mixin import VideoToolMixin
from .command_mixin import VideoCommandMixin

__all__ = [
    "VideoToolMixin",
    "VideoCommandMixin",
]