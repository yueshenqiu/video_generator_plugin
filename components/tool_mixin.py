"""Tool 组件业务逻辑 Mixin"""

from typing import Optional


class VideoToolMixin:
    """视频生成 Tool 业务逻辑
    
    通过 Mixin 模式注入到插件主类中。
    方法中可直接使用 self.ctx、self.task_manager 等属性。
    """

    async def _tool_video_generate(
        self,
        stream_id: str,
        prompt: str,
        duration: int = 5,
        resolution: str = "720p",
        **kwargs,
    ) -> dict:
        """
        智能视频生成 Tool 实现 - 文生视频
        
        Args:
            stream_id: 聊天流 ID
            prompt: 视频描述提示词
            duration: 时长（秒）
            resolution: 分辨率
            
        Returns:
            Tool 结果字典
        """
        if not prompt:
            await self.ctx.send.text("请告诉我你想生成什么样的视频呢？", stream_id)
            return {"success": False, "message": "未提供视频描述"}

        if not self.task_manager:
            await self.ctx.send.text("视频生成服务暂时不可用，请稍后再试~", stream_id)
            return {"success": False, "message": "插件未初始化"}

        task_id = await self.task_manager.submit_task(
            task_type="text2video",
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            chat_id=stream_id,
            user_id="",
        )

        if task_id:
            queue_position = self.task_manager.get_queue_position(task_id)
            if queue_position > 0:
                msg = (
                    f"✨ 文生视频任务已提交！\n"
                    f"📋 任务ID: {task_id}\n"
                    f"📝 描述: {prompt[:50]}{'...' if len(prompt) > 50 else ''}\n"
                    f"⏳ 当前排队位置: 第{queue_position}位\n"
                    f"💡 使用 /vg s 查看生成进度"
                )
            else:
                msg = (
                    f"✨ 文生视频任务已开始！\n"
                    f"📋 任务ID: {task_id}\n"
                    f"📝 描述: {prompt[:50]}{'...' if len(prompt) > 50 else ''}\n"
                    f"💡 使用 /vg s 查看生成进度"
                )
            await self.ctx.send.text(msg, stream_id)
            self.ctx.logger.info(f"文生视频任务已提交: {task_id}")
            return {"success": True, "message": f"已提交文生视频任务: {task_id}"}
        else:
            await self.ctx.send.text("视频生成任务提交失败，队列可能已满，请稍后重试~", stream_id)
            return {"success": False, "message": "任务提交失败"}