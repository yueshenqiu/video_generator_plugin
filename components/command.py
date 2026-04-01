"""视频生成 Command 组件"""

from typing import Tuple, Optional, List

from src.plugin_system import BaseCommand
from src.common.logger import get_logger

from ..core.resolution_validator import ResolutionValidator
from ..core.image_utils import ImageProcessor
from ..constants.music_styles import MUSIC_STYLES
from ..constants.help_texts import HELP_TEXT, MUSIC_STYLES_TEXT, CAPS_HELP_TEXT
from . import get_plugin, get_task_manager, get_video_generator, get_template_manager


logger = get_logger("video_generator.command")

# 固定的有效参数值
VALID_FPS = [24, 30]
VALID_DURATION = [5, 10, 15]


class VideoGeneratorCommand(BaseCommand):
    """视频生成命令"""

    command_name = "video_generator"
    command_description = "视频生成相关命令"
    command_pattern = r"(?:.*，说：\s*)?/vg(?:\s+(?P<args>.*))?$"

    def _get_chat_id(self) -> Optional[str]:
        """获取当前聊天流ID"""
        try:
            chat_stream = self.message.chat_stream if self.message else None
            return chat_stream.stream_id if chat_stream else None
        except Exception:
            return None

    def _get_user_id(self) -> Optional[str]:
        """获取用户ID"""
        try:
            if self.message and self.message.message_info and self.message.message_info.user_info:
                return str(self.message.message_info.user_info.user_id)
            return None
        except Exception:
            return None

    def _check_admin_permission(self) -> bool:
        """检查用户是否有管理员权限"""
        try:
            plugin = get_plugin()
            if not plugin:
                return False
            
            admin_users = plugin.get_config("admin.admin_users", [])
            user_id = self._get_user_id()
            
            if not user_id:
                return False
            return user_id in admin_users
        except Exception:
            return False

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        """执行命令"""
        plugin = get_plugin()
        if not plugin:
            logger.error("[Command] 插件实例为空")
            await self.send_text("❌ 插件未初始化，请检查日志")
            return False, "插件实例为空", True
        
        args_str = self.matched_groups.get("args", "") or ""
        args = args_str.strip().split() if args_str.strip() else []

        if not args:
            return await self._show_help()

        sub_command = args[0].lower()

        command_handlers = {
            "help": self._show_help,
            "h": self._show_help,
            "c": self._show_config,
            "m": self._show_models,
            "t": self._show_templates,
            "s": self._show_status,
            "y": self._show_music_styles,
            "caps": lambda: self._show_capabilities(args[1:]),
            "w": lambda: self._switch_model(args[1:]),
            "d": lambda: self._cancel_task(args[1:]),
        }

        if sub_command in command_handlers:
            admin_commands = ["w", "d"]
            if sub_command in admin_commands and not self._check_admin_permission():
                await self.send_text("❌ 你没有权限执行此命令")
                return False, "没有权限", True
            return await command_handlers[sub_command]()
        else:
            return await self._generate_video(args)

    async def _show_help(self) -> Tuple[bool, Optional[str], bool]:
        """显示帮助信息"""
        await self.send_text(HELP_TEXT)
        return True, "显示帮助", True

    async def _show_config(self) -> Tuple[bool, Optional[str], bool]:
        """显示当前配置"""
        video_generator = get_video_generator()
        if not video_generator:
            await self.send_text("❌ 视频生成器未初始化")
            return False, "未初始化", True

        current_model_id = video_generator.get_current_model_id()
        current_config = video_generator.get_current_model_config()
        
        model_name = current_config.get("name", current_model_id)
        model_format = current_config.get("format", "unknown")
        default_resolution = current_config.get("default_resolution", "720p")
        default_duration = current_config.get("default_duration", 5)

        config_text = f"""⚙️ 当前配置

【当前模型】
🎬 模型ID: {current_model_id}
📛 名称: {model_name}
🏢 服务商: {model_format}
📐 默认分辨率: {default_resolution}
⏱️ 默认时长: {default_duration}秒

💡 使用 /vg m 查看所有模型
💡 使用 /vg caps 查看模型能力
💡 使用 /vg s 查看任务队列"""

        await self.send_text(config_text)
        return True, "显示配置", True

    async def _show_models(self) -> Tuple[bool, Optional[str], bool]:
        """显示可用模型"""
        video_generator = get_video_generator()
        if not video_generator:
            await self.send_text("❌ 视频生成器未初始化")
            return False, "未初始化", True

        model_list = video_generator.get_model_list()
        
        if not model_list:
            await self.send_text("❌ 没有配置任何模型")
            return False, "无模型", True

        model_text = "🎬 可用模型列表\n\n"
        
        for model in model_list:
            current_mark = "✅" if model["is_current"] else "  "
            api_mark = "🔑" if model["has_api_key"] else "❌"
            img2video_mark = "🖼️" if model["support_img2video"] else ""
            
            model_text += f"{current_mark} {model['id']}\n"
            model_text += f"   📛 {model['name']}\n"
            model_text += f"   🏢 {model['format']} {api_mark} {img2video_mark}\n\n"

        model_text += "图例:✅当前 🔑已配置 🖼️支持图生视频\n"
        model_text += "💡 /vg w<模型ID> 切换模型\n"
        model_text += "💡 /vg caps<模型ID> 查看能力"
        
        await self.send_text(model_text)
        return True, "显示模型", True

    async def _show_capabilities(self, args: List[str]) -> Tuple[bool, Optional[str], bool]:
        """显示模型能力"""
        video_generator = get_video_generator()
        if not video_generator:
            await self.send_text("❌ 视频生成器未初始化")
            return False, "未初始化", True

        if args:
            model_id = args[0]
            model_config = video_generator.get_model_config(model_id)
            if not model_config:
                await self.send_text(f"❌ 模型 {model_id} 不存在\n💡 /vg m 查看可用模型")
                return False, "模型不存在", True
            
            caps = video_generator.get_model_capabilities(model_id)
            if caps:
                caps_text = self._format_model_capabilities(model_id, model_config, caps)
            else:
                caps_text = self._format_basic_model_info(model_id, model_config)
        else:
            model_id = video_generator.get_current_model_id()
            model_config = video_generator.get_current_model_config()
            caps = video_generator.get_model_capabilities(model_id)
            
            if caps:
                caps_text = self._format_model_capabilities(model_id, model_config, caps)
            else:
                caps_text = self._format_basic_model_info(model_id, model_config)
        
        await self.send_text(caps_text)
        return True, "显示能力", True

    def _format_model_capabilities(self, model_id: str, config: dict, caps: dict) -> str:
        """格式化模型能力信息"""
        name = config.get("name", model_id)
        
        video_features = caps.get("video_features", [])
        feature_icons = {
            "TEXT_TO_VIDEO": "📝 文生视频",
            "IMAGE_TO_VIDEO": "🖼️ 图生视频",
            "FIRST_FRAME": "🎬 首帧控制",
            "LAST_FRAME": "🎞️ 尾帧控制",
            "VIDEO_EXTEND": "📹 视频续写",
            "MULTI_SHOT": "🎥 多镜头叙事",
            "CAMERA_CONTROL": "📷 镜头控制",
        }
        
        features_text = ""
        for feature in video_features:
            icon = feature_icons.get(feature, f"• {feature}")
            features_text += f"{icon}\n"
        
        if not features_text:
            features_text = "  暂无信息\n"
        
        audio_features = caps.get("audio_features", [])
        audio_icons = {
            "BACKGROUND_MUSIC": "🎵 背景音乐",
            "AUDIO_INPUT": "🎧 自定义音频",
            "AUTO_SOUND": "🔊 自动音效",
            "LIP_SYNC": "👄 口型同步",
        }
        
        audio_text = ""
        for feature in audio_features:
            icon = audio_icons.get(feature, f"• {feature}")
            audio_text += f"  {icon}\n"
        
        if not audio_text:
            audio_text = "  ❌ 不支持音频\n"
        
        resolutions = caps.get("resolutions", ["720p", "1080p"])
        duration_range = caps.get("duration_range", "5秒")
        fps_list = caps.get("fps", [24, 30])
        
        text = f"""🔍 模型能力: {name}
📋 ID: {model_id}

【视频特性】
{features_text}
【音频特性】
{audio_text}
【参数范围】
  📐 分辨率: {', '.join(resolutions)}
  ⏱️ 时长: {duration_range}
  🎞️ 帧率: {', '.join(map(str, fps_list))} fps

💡 /vg caps <模型ID> 查看其他模型"""
        
        return text

    def _format_basic_model_info(self, model_id: str, config: dict) -> str:
        """格式化基本模型信息"""
        name = config.get("name", model_id)
        format_name = config.get("format", "unknown")
        support_img = "✅" if config.get("support_img2video", True) else "❌"
        
        return f"""🔍 模型信息: {name}
📋 ID: {model_id}
🏢 服务商: {format_name}
🖼️ 图生视频: {support_img}

⚠️ 详细能力信息暂不可用"""

    async def _show_templates(self) -> Tuple[bool, Optional[str], bool]:
        """显示预设模板"""
        template_manager = get_template_manager()
        if not template_manager:
            await self.send_text("❌ 模板管理器未初始化")
            return False, "未初始化", True

        templates = template_manager.get_all_templates()
        
        if not templates:
            await self.send_text("📋 暂无预设模板\n\n💡 可在配置文件中添加")
            return True, "无模板", True

        template_text = "📋 预设模板列表\n\n"
        
        for keyword_lower, template in templates.items():
            keyword = template.get('keyword', keyword_lower)
            description = template.get('description', '')
            template_text += f"🔑 {keyword}"
            if description:
                template_text += f" - {description}"
            template_text += "\n"

        template_text += f"\n共{len(templates)} 个模板\n"
        template_text += "💡 /vg <关键词> 快速生成"
        
        await self.send_text(template_text)
        return True, "显示模板", True

    async def _show_status(self) -> Tuple[bool, Optional[str], bool]:
        """显示任务状态"""
        task_manager = get_task_manager()
        if not task_manager:
            await self.send_text("❌ 任务管理器未初始化")
            return False, "未初始化", True

        status = task_manager.get_all_status()
        
        if not status["running"] and not status["queued"]:
            await self.send_text("📊 当前没有进行中的任务")
            return True, "无任务", True

        status_text = "📊 任务状态\n\n"

        if status["running"]:
            status_text += "【正在生成】\n"
            for task in status["running"]:
                progress = task.get("progress", 0)
                task_type = "🖼️" if task.get("task_type") == "image2video" else "📝"
                poll_count = task.get("poll_count", 0)
                status_text += f"{task_type} {task['id']}\n"
                status_text += f"   进度: {'█' * (progress // 10)}{'░' * (10 - progress // 10)} {progress}%\n"
                status_text += f"   {task.get('prompt', '')[:25]}...\n"
                status_text += f"   轮询: {poll_count}次\n\n"

        if status["queued"]:
            status_text += "【排队中】\n"
            for i, task in enumerate(status["queued"], 1):
                task_type = "🖼️" if task.get("task_type") == "image2video" else "📝"
                status_text += f"⏳ 第{i}位: {task_type} {task['id']}\n"

        await self.send_text(status_text)
        return True, "显示状态", True

    async def _show_music_styles(self) -> Tuple[bool, Optional[str], bool]:
        """显示音乐风格列表"""
        await self.send_text(MUSIC_STYLES_TEXT)
        return True, "显示音乐风格", True

    async def _switch_model(self, args: List[str]) -> Tuple[bool, Optional[str], bool]:
        """切换模型"""
        if not args:
            await self.send_text("❌ 请指定模型ID\n💡 /vg m 查看可用模型")
            return False, "未指定模型", True

        model_id = args[0]
        video_generator = get_video_generator()
        
        if not video_generator:
            await self.send_text("❌ 视频生成器未初始化")
            return False, "未初始化", True

        success = video_generator.switch_model(model_id)
        if success:
            model_config = video_generator.get_model_config(model_id)
            model_name = model_config.get("name", model_id) if model_config else model_id
            await self.send_text(f"✅ 已切换到: {model_name}\n💡 /vg caps查看模型能力")
            logger.info(f"[Command] 切换模型: {model_id}")
            return True, f"切换模型 {model_id}", True
        else:
            await self.send_text(f"❌ 模型 {model_id} 不可用\n💡 /vg m 查看可用模型")
            return False, "模型不可用", True

    async def _cancel_task(self, args: List[str]) -> Tuple[bool, Optional[str], bool]:
        """取消任务"""
        if not args:
            await self.send_text("❌ 请指定任务ID\n💡 /vg s 查看任务列表")
            return False, "未指定任务", True

        task_id = args[0]
        task_manager = get_task_manager()
        
        if not task_manager:
            await self.send_text("❌ 任务管理器未初始化")
            return False, "未初始化", True

        success, message = await task_manager.cancel_task(task_id)
        if success:
            await self.send_text(f"✅ {message}")
            logger.info(f"[Command] 取消任务: {task_id}")
            return True, f"取消任务 {task_id}", True
        else:
            await self.send_text(f"❌ {message}")
            return False, message, True

    async def _generate_video(self, args: List[str]) -> Tuple[bool, Optional[str], bool]:
        """解析参数并生成视频"""
        plugin = get_plugin()
        task_manager = get_task_manager()
        
        if not plugin:
            await self.send_text("❌ 插件未初始化")
            return False, "插件未初始化", True

        if not task_manager:
            await self.send_text("❌ 任务管理器未初始化")
            return False, "任务管理器未初始化", True

        default_resolution = plugin.get_config("generation.default_resolution", "720p")
        default_fps = plugin.get_config("generation.default_fps", 24)
        default_duration = plugin.get_config("generation.default_duration", 5)
        
        resolution = default_resolution
        fps = default_fps
        duration = default_duration
        prompt_parts = []
        frame_mode = None
        music_enabled = False
        music_volume = 50
        music_style = None

        i = 0
        while i < len(args):
            arg = args[i]
            arg_lower = arg.lower()

            if arg_lower == "f":
                frame_mode = "f"
            elif arg_lower == "r":
                frame_mode = "r"
            elif arg_lower == "fr":
                frame_mode = "fr"
            elif arg_lower in ["720p", "1080p", "480p", "4k"]:
                resolution = arg_lower
            elif ResolutionValidator.is_custom_resolution(arg):
                if ResolutionValidator.validate_custom_resolution(arg):
                    resolution = arg
                else:
                    await self.send_text(f"❌ 分辨率 {arg} 不合法")
                    return False, "分辨率不合法", True
            elif arg_lower.startswith("mu") and len(arg_lower) > 2:
                try:
                    vol = int(arg_lower[2:])
                    if 0 <= vol <= 100:
                        music_enabled = True
                        music_volume = vol
                    else:
                        prompt_parts.append(arg)
                except ValueError:
                    prompt_parts.append(arg)
            elif arg_lower == "mu":
                music_enabled = True
            elif arg_lower in MUSIC_STYLES:
                music_enabled = True
                music_style = arg_lower
            elif arg.isdigit() and int(arg) in VALID_FPS:
                fps = int(arg)
            elif arg.isdigit():
                parsed = ResolutionValidator.parse_duration(arg)
                if parsed and int(arg) not in VALID_FPS:
                    duration = parsed
                else:
                    prompt_parts.append(arg)
            else:
                prompt_parts.append(arg)
            i += 1

        full_prompt = " ".join(prompt_parts)
        video_prompt = full_prompt
        
        if "-" in full_prompt and music_enabled:
            parts = full_prompt.rsplit("-", 1)
            if len(parts) == 2:
                video_prompt = parts[0].strip()

        if not video_prompt:
            await self.send_text("❌ 请提供视频描述\n💡 /vg help 查看帮助")
            return False, "未提供描述", True

        is_template = False
        template_manager = get_template_manager()
        if template_manager:
            template = template_manager.get_template(video_prompt)
            if template:
                is_template = True
                video_prompt = template.get("prompt", video_prompt)
                resolution = template.get("resolution", resolution)
                fps = template.get("fps", fps)
                duration = template.get("duration", duration)

        chat_id = self._get_chat_id()
        user_id = self._get_user_id()

        if not chat_id:
            await self.send_text("❌ 无法获取聊天信息")
            return False, "无法获取chat_id", True

        image_processor = ImageProcessor(self)
        first_frame_url = None
        last_frame_url = None
        task_type = "text2video"
        mode_text = "文生视频"

        if frame_mode == "fr":
            images = await image_processor.get_recent_images(count=2)
            if len(images) >= 2:
                first_frame_url = images[0]
                last_frame_url = images[1]
                task_type = "image2video"
                mode_text = "首尾帧图生视频"
            elif len(images) == 1:
                first_frame_url = images[0]
                task_type = "image2video"
                mode_text = "首帧图生视频（仅1张图）"
            else:
                await self.send_text("❌ 首尾帧模式需要2张图片")
                return False, "图片不足", True
        elif frame_mode == "f":
            first_frame_url = await image_processor.get_recent_image_url()
            if first_frame_url:
                task_type = "image2video"
                mode_text = "首帧图生视频"
        elif frame_mode == "r":
            last_frame_url = await image_processor.get_recent_image_url()
            if last_frame_url:
                task_type = "image2video"
                mode_text = "尾帧图生视频"
        else:
            first_frame_url = await image_processor.get_recent_image_url()
            if first_frame_url:
                task_type = "image2video"
                mode_text = "图生视频"

        task_id = await task_manager.submit_task(
            task_type=task_type,
            prompt=video_prompt,
            resolution=resolution,
            fps=fps,
            duration=duration,
            image_url=first_frame_url,
            last_frame_url=last_frame_url,
            chat_id=chat_id,
            user_id=user_id or "",
            music_enabled=music_enabled,
            music_style=music_style,
            music_volume=music_volume,)

        if task_id:
            queue_position = task_manager.get_queue_position(task_id)
            template_text = "📋 预设模板\n" if is_template else ""
            music_text = f"🎵 {music_style or '默认'}({music_volume}%)\n" if music_enabled else ""
            
            msg = f"✨ {mode_text}已提交！\n{template_text}{music_text}📋 ID: {task_id}\n"
            if queue_position > 0:
                msg += f"⏳ 排队:第{queue_position}位\n"
            msg += "💡 /vg s 查看进度"
            
            await self.send_text(msg)
            return True, f"提交 {task_id}", True
        else:
            await self.send_text("❌ 任务提交失败，队列可能已满")
            return False, "提交失败", True