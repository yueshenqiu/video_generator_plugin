"""视频生成 Action 组件"""

from typing import Tuple, Optional

from src.plugin_system import BaseAction, ActionActivationType
from src.common.logger import get_logger

from . import get_plugin, get_task_manager


logger = get_logger("video_generator.action")


class VideoGenerateAction(BaseAction):
    """智能视频生成Action - 识别用户意图自动生成视频（文生视频）"""

    action_name = "video_generate"
    action_description = "根据用户描述智能生成视频"
    activation_type = ActionActivationType.KEYWORD
    activation_keywords = [
        "生成视频", "帮我生成", "做个视频", "创建视频",
        "制作视频", "生成一个", "做一个视频"
    ]
    keyword_case_sensitive = False

    associated_types = ["text", "videourl"]
    parallel_action = False

    action_parameters = {
        "prompt": "视频生成的提示词描述",
        "duration": "视频时长（秒），可选",
        "resolution": "分辨率，可选，如720p、1080p"
    }

    action_require = [
        "当用户明确要求生成视频时使用",
        "当用户说'帮我生成xxx的视频'时使用",
        "当用户说'生成xxx的视频'时使用",
        "当用户说'做一个xxx视频'时使用",
        "不要在用户询问视频相关问题但不需要生成时使用"
    ]

    def _get_chat_id(self) -> Optional[str]:
        """获取当前聊天流ID"""
        try:
            if hasattr(self, 'chat_stream') and self.chat_stream:
                return self.chat_stream.stream_id
            return None
        except Exception:
            return None

    def _get_user_id(self) -> Optional[str]:
        """获取用户ID"""
        try:
            if hasattr(self, 'user_id'):
                return str(self.user_id)
            return None
        except Exception:
            return None

    async def execute(self) -> Tuple[bool, str]:
        """执行视频生成（文生视频）"""
        prompt = self.action_data.get("prompt", "")
        if not prompt:
            await self.send_text("请告诉我你想生成什么样的视频呢？")
            return False, "未提供视频描述"

        duration = self.action_data.get("duration", 5)
        resolution = self.action_data.get("resolution", "720p")

        # 使用辅助函数获取实例
        plugin = get_plugin()
        if not plugin:
            logger.error("[Action] 插件实例为空")
            await self.send_text("视频生成服务暂时不可用，请稍后再试~")
            return False, "插件实例为空"
        
        task_manager = get_task_manager()
        if not task_manager:
            logger.error("[Action] 任务管理器未初始化")
            await self.send_text("视频生成服务暂时不可用，请稍后再试~")
            return False, "任务管理器未初始化"

        chat_id = self._get_chat_id()
        user_id = self._get_user_id()
        
        if not chat_id:
            await self.send_text("无法获取聊天信息，请稍后再试~")
            return False, "无法获取chat_id"

        task_id = await task_manager.submit_task(
            task_type="text2video",
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            chat_id=chat_id,
            user_id=user_id or ""
        )

        if task_id:
            queue_position = task_manager.get_queue_position(task_id)
            if queue_position > 0:
                await self.send_text(
                    f"✨ 文生视频任务已提交！\n"
                    f"📋 任务ID: {task_id}\n"
                    f"📝 描述: {prompt[:50]}{'...' if len(prompt) > 50 else ''}\n"
                    f"⏳ 当前排队位置: 第{queue_position}位\n"
                    f"💡 使用 /vg s 查看生成进度"
                )
            else:
                await self.send_text(
                    f"✨ 文生视频任务已开始！\n"
                    f"📋 任务ID: {task_id}\n"
                    f"📝 描述: {prompt[:50]}{'...' if len(prompt) > 50 else ''}\n"
                    f"💡 使用 /vg s 查看生成进度"
                )
            logger.info(f"[Action] 文生视频任务已提交: {task_id}")
            return True, f"已提交文生视频任务: {task_id}"
        else:
            await self.send_text("视频生成任务提交失败，队列可能已满，请稍后重试~")
            return False, "任务提交失败"