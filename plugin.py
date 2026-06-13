"""视频生成插件主入口 - 新版 SDK（Mixin 模式）"""

from typing import Any, Optional, Dict, List, ClassVar

from maibot_sdk import MaiBotPlugin, Tool, Command
from maibot_sdk.types import ToolParameterInfo, ToolParamType

from .constants.config_schema import VideoGeneratorConfig
from .core.generator import VideoGenerator
from .core.task_manager import TaskManager
from .core.template_manager import TemplateManager
from .core.config_validator import ConfigValidator
from .core.video_downloader import VideoDownloader
from .components.tool_mixin import VideoToolMixin
from .components.command_mixin import VideoCommandMixin


class VideoGeneratorPlugin(VideoToolMixin, VideoCommandMixin, MaiBotPlugin):
    """视频生成插件 - 支持文生视频/图生视频，多服务商，任务队列

    通过 Mixin 模式组织代码：
    - VideoToolMixin: Tool 组件的业务逻辑
    - VideoCommandMixin: Command 组件的业务逻辑
    - 本文件: 生命周期、初始化、装饰器声明
    """

    config_model = VideoGeneratorConfig

    # 订阅全局模型配置热重载（LLM 模型变更时通知）
    config_reload_subscriptions: ClassVar[tuple[str, ...]] = ("model",)

    # 运行时属性
    task_manager: Optional[TaskManager] = None
    video_generator: Optional[VideoGenerator] = None
    template_manager: Optional[TemplateManager] = None
    video_downloader: Optional[VideoDownloader] = None

    # ==================== 生命周期 ====================

    async def on_load(self) -> None:
        """插件加载时初始化"""
        self.ctx.logger.info("视频生成插件加载中...")
        self._ensure_initialized()
        self.ctx.logger.info("视频生成插件加载完成")

    async def on_unload(self) -> None:
        """插件卸载时清理资源"""
        self.ctx.logger.info("视频生成插件正在卸载...")
        if self.task_manager:
            await self.task_manager.stop()
        self.ctx.logger.info("视频生成插件已卸载")

    async def on_config_update(self, scope: str, config_data: dict, version: str) -> None:
        """配置热更新回调"""
        if scope == "self":
            self.ctx.logger.info("插件配置已更新: version=%s，执行热重载", version)
            await self._hot_reload()
        elif scope == "model":
            self.ctx.logger.info("全局模型配置已更新: version=%s", version)
            # 模型配置变更时也重新初始化（可能影响 LLM Tool 调用行为）

    # ==================== 热重载 ====================

    async def _hot_reload(self) -> None:
        """热重载：停止现有服务 → 重新初始化"""
        self.ctx.logger.info("执行热重载...")

        # 停止任务管理器（等待当前任务完成或取消）
        if self.task_manager:
            await self.task_manager.stop()

        # 清空运行时实例
        self.task_manager = None
        self.video_generator = None
        self.template_manager = None

        # 重新初始化
        success = self._ensure_initialized()
        if success:
            self.ctx.logger.info("热重载完成")
        else:
            self.ctx.logger.error("热重载失败，插件可能不可用")

    # ==================== 初始化 ====================

    def _ensure_initialized(self) -> bool:
        """确保插件已初始化"""
        if self.task_manager is not None:
            return True

        try:
            self.ctx.logger.debug("开始初始化...")

            # 配置验证
            ConfigValidator.validate_and_log(self.config, self.ctx.logger)

            # 初始化模板管理器
            templates_data = self._get_templates_list()
            self.template_manager = TemplateManager(templates_data, logger=self.ctx.logger)

            # 获取模型配置
            models_config = self._load_models_config()
            default_model = self.config.generation.default_model

            # 初始化视频生成器
            self.video_generator = VideoGenerator(
                models_config=models_config,
                default_model=default_model,
                logger=self.ctx.logger,
            )

            # 初始化视频下载器
            self.video_downloader = VideoDownloader(logger=self.ctx.logger)

            # 初始化任务管理器
            self.task_manager = TaskManager(
                video_generator=self.video_generator,
                max_queue_size=self.config.queue.max_queue_size,
                task_timeout=self.config.queue.task_timeout,
                poll_interval=self.config.queue.poll_interval,
                send_callback=self._send_to_chat,
                video_downloader=self.video_downloader,
                logger=self.ctx.logger,
            )

            # 汇总一行关键信息
            total_models = len(self.video_generator._models_config)
            configured = sum(
                1 for c in self.video_generator._models_config.values()
                if isinstance(c, dict) and c.get("api_key")
            )
            template_count = self.template_manager.get_template_count() if self.template_manager else 0
            self.ctx.logger.info(
                f"初始化完成: {total_models} 个模型 ({configured} 已配置), "
                f"{template_count} 个模板, 默认 {default_model}"
            )
            return True

        except Exception as e:
            self.ctx.logger.error(f"初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _get_templates_list(self) -> List[Dict[str, Any]]:
        """从配置获取模板列表（转为 dict 列表）"""
        try:
            template_items = self.config.templates.template_list
            return [
                {
                    "keyword": t.keyword,
                    "description": t.description,
                    "prompt": t.prompt,
                    "resolution": t.resolution,
                    "fps": t.fps,
                    "duration": t.duration,
                }
                for t in template_items
            ]
        except Exception:
            return []

    def _load_models_config(self) -> Dict[str, Dict[str, Any]]:
        """加载模型配置（支持动态模型数量）"""
        models_config = {}
        models_section = self.config.models

        # 动态发现所有 model 属性，不硬编码数量
        model_keys = sorted(
            (k for k in dir(models_section) if k.startswith("model") and k[5:].isdigit()),
            key=lambda x: int(x[5:]),
        )

        for model_key in model_keys:
            model_cfg = getattr(models_section, model_key, None)
            if model_cfg is None:
                continue

            if model_cfg.format:
                models_config[model_key] = {
                    "name": model_cfg.name,
                    "format": model_cfg.format,
                    "base_url": model_cfg.base_url,
                    "api_key": model_cfg.api_key,
                    "model": model_cfg.model,
                    "default_resolution": model_cfg.default_resolution,
                    "default_duration": model_cfg.default_duration,
                    "prompt_extend": model_cfg.prompt_extend,
                    "watermark": model_cfg.watermark,
                    "support_img2video": model_cfg.support_img2video,
                }
                self.ctx.logger.debug(f"加载模型: {model_key}")

        if not models_config:
            self.ctx.logger.warning("没有找到有效的模型配置")

        return models_config

    # ==================== 消息发送 ====================

    async def _send_to_chat(self, chat_id: str, message_type: str, content: str) -> None:
        """发送消息到指定聊天（作为 TaskManager 的回调）"""
        try:
            if message_type == "text":
                success = await self.ctx.send.text(content, chat_id)
            elif message_type == "file":
                success = await self.ctx.send.custom(
                    custom_type="file",
                    data={"path": content},
                    stream_id=chat_id,
                )
            elif message_type == "videourl":
                success = await self.ctx.send.text(f"🎬 视频链接:\n{content}", chat_id)
            else:
                success = await self.ctx.send.text(content, chat_id)

            if not success:
                self.ctx.logger.error(f"发送失败: [{message_type}]")

        except Exception as e:
            self.ctx.logger.error(f"发送异常: {e}")

    # ==================== 辅助方法 ====================

    def _check_admin_permission(self, user_id: Optional[str]) -> bool:
        """检查用户是否有管理员权限"""
        if not user_id:
            return False
        try:
            admin_users = self.config.admin.admin_users
            return user_id in admin_users
        except Exception:
            return False

    # ==================== 组件声明（薄代理层） ====================

    @Tool(
        "video_generate",
        brief_description="根据用户描述智能生成视频",
        detailed_description=(
            "当用户明确要求生成视频时使用此工具。\n"
            "适用场景：用户说'帮我生成xxx的视频'、'生成xxx的视频'、'做一个xxx视频'等。\n"
            "不要在用户仅询问视频相关问题但不需要生成时使用。\n\n"
            "参数说明：\n"
            "- stream_id：string，必填。当前聊天流 ID。\n"
            "- prompt：string，必填。视频生成的提示词描述。\n"
            "- duration：integer，可选。视频时长（秒），默认 5。\n"
            "- resolution：string，可选。分辨率，如 720p、1080p，默认 720p。"
        ),
        parameters=[
            ToolParameterInfo(
                name="stream_id",
                param_type=ToolParamType.STRING,
                description="当前聊天流 ID",
                required=True,
            ),
            ToolParameterInfo(
                name="prompt",
                param_type=ToolParamType.STRING,
                description="视频生成的提示词描述",
                required=True,
            ),
            ToolParameterInfo(
                name="duration",
                param_type=ToolParamType.INTEGER,
                description="视频时长（秒）",
                required=False,
                default=5,
            ),
            ToolParameterInfo(
                name="resolution",
                param_type=ToolParamType.STRING,
                description="分辨率，如 720p、1080p",
                required=False,
                default="720p",
            ),
        ],
    )
    async def handle_video_generate(
        self,
        stream_id: str,
        prompt: str,
        duration: int = 5,
        resolution: str = "720p",
        **kwargs,
    ):
        """Tool 入口 → 委托到 Mixin"""
        return await self._tool_video_generate(
            stream_id=stream_id,
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            **kwargs,
        )

    @Command("vg", pattern=r"(?:.*，说：\s*)?/vg(?:\s+(?P<args>.*))?$")
    async def handle_vg_command(self, **kwargs):
        """Command 入口 → 委托到 Mixin"""
        stream_id = kwargs.get("stream_id", "")
        matched_groups = kwargs.get("matched_groups", {})
        args_str = matched_groups.get("args", "") or ""
        args = args_str.strip().split() if args_str.strip() else []

        return await self._cmd_dispatch(stream_id, args, kwargs)


def create_plugin():
    return VideoGeneratorPlugin()