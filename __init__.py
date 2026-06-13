"""视频生成插件 - 支持多服务商的 AI 视频生成

提供文生视频、图生视频、首尾帧控制等功能，
支持火山引擎、阿里云、可灵、智谱等服务商。
"""

from .plugin import VideoGeneratorPlugin, create_plugin

__all__ = [
    "VideoGeneratorPlugin",
    "create_plugin",
]