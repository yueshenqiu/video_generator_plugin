"""视频生成插件主入口"""

from typing import List, Tuple, Type, Optional, Dict, Any

from src.plugin_system import (
    BasePlugin,
    register_plugin,
    ComponentInfo,
)
from src.common.logger import get_logger

from .constants.config_schema import CONFIG_SCHEMA, CONFIG_SECTIONS, CONFIG_LAYOUT
from .core.generator import VideoGenerator
from .core.task_manager import TaskManager
from .core.template_manager import TemplateManager
from .core.config_validator import ConfigValidator


logger = get_logger("video_generator")


# ==================== 插件主类 ====================

@register_plugin
class VideoGeneratorPlugin(BasePlugin):
    """视频生成插件"""

    plugin_name = "video_generator_plugin"
    enable_plugin = True
    dependencies = []
    python_dependencies = ["dashscope", "volcengine-python-sdk[ark]", "aiohttp", "aiofiles"]
    config_file_name = "config.toml"

    # 从 constants 导入配置定义
    config_section_descriptions = CONFIG_SECTIONS
    config_schema = CONFIG_SCHEMA
    config_layout = CONFIG_LAYOUT

    # 运行时属性
    task_manager: Optional[TaskManager] = None
    video_generator: Optional[VideoGenerator] = None
    template_manager: Optional[TemplateManager] = None

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回插件组件"""
        # 设置插件实例 - 使用延迟导入
        from . import instance
        instance.set_plugin_instance(self)
        logger.info("[VideoGeneratorPlugin] 插件实例已设置")
        
        # 初始化
        self._ensure_initialized()
        
        # 延迟导入组件
        from .components import VideoGenerateAction, VideoGeneratorCommand
        
        return [
            (VideoGenerateAction.get_action_info(), VideoGenerateAction),
            (VideoGeneratorCommand.get_command_info(), VideoGeneratorCommand),
        ]

    def _ensure_initialized(self) -> bool:
        """确保插件已初始化"""
        if self.task_manager is not None:
            return True
        
        try:
            logger.info("[VideoGeneratorPlugin] 开始初始化...")
            
            # 配置验证
            ConfigValidator.validate_and_log(self)
            
            # 初始化模板管理器
            templates = self.get_config("templates.template_list", [])
            if templates is None:
                templates = []
            self.template_manager = TemplateManager(templates)

            # 获取模型配置
            models_config = self._load_models_config()
            default_model = self.get_config("generation.default_model", "model1")
            
            # 初始化视频生成器
            self.video_generator = VideoGenerator(
                models_config=models_config,
                default_model=default_model,
            )

            # 初始化任务管理器
            self.task_manager = TaskManager(
                video_generator=self.video_generator,
                max_queue_size=self.get_config("queue.max_queue_size", 10),
                task_timeout=self.get_config("queue.task_timeout", 600),
                poll_interval=self.get_config("queue.poll_interval", 5),
                plugin=self,
            )

            logger.info("[VideoGeneratorPlugin] 初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"[VideoGeneratorPlugin] 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _load_models_config(self) -> Dict[str, Dict[str, Any]]:
        """加载模型配置"""
        models_config = {}
        
        raw_models = self.get_config("models", {})
        
        if isinstance(raw_models, dict):
            for key, value in raw_models.items():
                if isinstance(value, dict) and "format" in value:
                    models_config[key] = value
                    logger.debug(f"[VideoGeneratorPlugin] 加载模型: {key}")
        
        if not models_config:
            logger.warning("[VideoGeneratorPlugin] 没有找到有效的模型配置")
        
        return models_config

    async def send_to_chat(self, chat_id: str, message_type: str, content: str):
        """发送消息到指定聊天"""
        try:
            from src.plugin_system.apis import send_api
            
            success = await send_api.custom_to_stream(
                message_type=message_type,
                content=content,
                stream_id=chat_id,
                display_message="",
                typing=False,
                storage_message=True,
                show_log=True
            )
            
            if success:
                logger.debug(f"[VideoGeneratorPlugin] 消息已发送: [{message_type}]")
            else:
                logger.error(f"[VideoGeneratorPlugin] 发送失败: [{message_type}]")
                
        except Exception as e:
            logger.error(f"[VideoGeneratorPlugin] 发送异常: {e}")