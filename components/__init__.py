"""组件模块初始化"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..plugin import VideoGeneratorPlugin
    from ..core.task_manager import TaskManager
    from ..core.generator import VideoGenerator
    from ..core.template_manager import TemplateManager


def get_plugin() -> Optional["VideoGeneratorPlugin"]:
    """获取插件实例的便捷方法"""
    from .. import instance
    return instance.get_plugin_instance()


def get_task_manager() -> Optional["TaskManager"]:
    """获取任务管理器"""
    plugin = get_plugin()
    return plugin.task_manager if plugin else None


def get_video_generator() -> Optional["VideoGenerator"]:
    """获取视频生成器"""
    plugin = get_plugin()
    return plugin.video_generator if plugin else None


def get_template_manager() -> Optional["TemplateManager"]:
    """获取模板管理器"""
    plugin = get_plugin()
    return plugin.template_manager if plugin else None


# 延迟导入组件类，避免循环导入
def _load_components():
    from .action import VideoGenerateAction
    from .command import VideoGeneratorCommand
    return VideoGenerateAction, VideoGeneratorCommand


# 为了保持向后兼容，在模块级别提供这些类
# 但使用延迟加载的方式
_components_loaded = False
_VideoGenerateAction = None
_VideoGeneratorCommand = None


def __getattr__(name):
    """延迟加载组件类"""
    global _components_loaded, _VideoGenerateAction, _VideoGeneratorCommand
    
    if name in ("VideoGenerateAction", "VideoGeneratorCommand"):
        if not _components_loaded:
            _VideoGenerateAction, _VideoGeneratorCommand = _load_components()
            _components_loaded = True
        
        if name == "VideoGenerateAction":
            return _VideoGenerateAction
        elif name == "VideoGeneratorCommand":
            return _VideoGeneratorCommand
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "VideoGenerateAction",
    "VideoGeneratorCommand",
    "get_plugin",
    "get_task_manager",
    "get_video_generator",
    "get_template_manager",
]