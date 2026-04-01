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

    def generate_default_config(self) -> str:
        """生成带详细注释的配置文件"""
        lines = [
            "# video_generator_plugin - 自动生成的配置文件",
            "# 支持文生视频/图生视频的多服务商视频生成插件,支持预设模板、热切换模型、任务队列等功能",
            ""
        ]
        
        # 按 order 排序 sections
        sections_order = sorted(
            self.config_section_descriptions.items(),
            key=lambda x: x[1].order
        )
        
        for section_key, section_info in sections_order:
            # 添加 ConfigSection 注释
            lines.append(f"# ConfigSection(title='{section_info.title}', description='{section_info.description}', icon='{section_info.icon}', collapsed={section_info.collapsed}, order={section_info.order})")
            lines.append(f"[{section_key}]")
            lines.append("")
            
            # 获取该 section 的字段
            section_fields = self.config_schema.get(section_key, {})
            
            # 按 order 排序字段
            fields_order = sorted(
                section_fields.items(),
                key=lambda x: x[1].order
            )
            
            for field_key, field_info in fields_order:
                # 添加字段注释
                if field_info.description:
                    lines.append(f"# {field_info.description}")
                
                # 根据类型生成值
                value = field_info.default
                if isinstance(value, str):
                    lines.append(f'{field_key} = "{value}"')
                elif isinstance(value, bool):
                    lines.append(f'{field_key} = {str(value).lower()}')
                elif isinstance(value, (int, float)):
                    lines.append(f'{field_key} = {value}')
                elif isinstance(value, list):
                    if not value:
                        lines.append(f'{field_key} = []')
                    else:
                        # 格式化列表
                        import json
                        lines.append(f'{field_key} = {json.dumps(value, ensure_ascii=False)}')
                else:
                    lines.append(f'{field_key} = {repr(value)}')
                
                lines.append("")
        
        return "\n".join(lines)

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