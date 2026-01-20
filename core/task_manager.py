"""任务管理器模块 - 支持智能轮询"""

import asyncio
import uuid
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from src.common.logger import get_logger
from .video_downloader import VideoDownloader

logger = get_logger("video_generator.task_manager")


class TaskStatus(Enum):
    """任务状态枚举"""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class VideoTask:
    """视频生成任务"""
    id: str
    task_type: str
    prompt: str
    resolution: str = "720p"
    fps: int = 24
    duration: int = 5
    image_url: Optional[str] = None
    last_frame_url: Optional[str] = None
    audio_url: Optional[str] = None
    chat_id: str = ""
    user_id: str = ""
    model_id: str = ""
    status: TaskStatus = TaskStatus.QUEUED
    progress: int = 0
    provider_task_id: str = ""
    video_url: str = ""
    local_video_path: str = ""
    error_message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_progress_update: float = 0
    music_enabled: bool = False
    music_style: Optional[str] = None
    music_volume: int = 50
    # 轮询相关
    poll_count: int = 0


class SmartPoller:
    """智能轮询器 - 指数退避"""
    
    def __init__(
        self,
        initial_interval: float = 2.0,
        max_interval: float = 30.0,
        multiplier: float = 1.5,
    ):
        """
        初始化智能轮询器
        
        Args:
            initial_interval: 初始轮询间隔（秒）
            max_interval: 最大轮询间隔（秒）
            multiplier: 间隔增长倍数
        """
        self.initial_interval = initial_interval
        self.max_interval = max_interval
        self.multiplier = multiplier
        self._current_interval = initial_interval
        self._poll_count = 0
    
    def get_interval(self) -> float:
        """获取当前轮询间隔"""
        return self._current_interval
    
    def next(self) -> float:
        """获取下一次轮询间隔并更新状态"""
        interval = self._current_interval
        self._poll_count += 1
        
        # 指数退避
        self._current_interval = min(
            self._current_interval * self.multiplier,
            self.max_interval
        )
        
        return interval
    
    def reset(self):
        """重置轮询状态"""
        self._current_interval = self.initial_interval
        self._poll_count = 0
    
    def fast_poll(self):
        """切换到快速轮询模式（接近完成时）"""
        self._current_interval = self.initial_interval


class TaskManager:
    """任务管理器 - 支持智能轮询"""

    def __init__(
        self,
        video_generator,
        max_queue_size: int = 10,
        task_timeout: int = 600,
        poll_interval: int = 5,
        plugin=None,
    ):
        self._video_generator = video_generator
        self._max_queue_size = max_queue_size
        self._task_timeout = task_timeout
        self._base_poll_interval = poll_interval
        self._plugin = plugin

        self._task_queue: List[VideoTask] = []
        self._running_task: Optional[VideoTask] = None
        self._completed_tasks: Dict[str, VideoTask] = {}

        self._running = False
        self._process_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        self._video_downloader = VideoDownloader()
        
        # 智能轮询器
        self._poller = SmartPoller(
            initial_interval=2.0,
            max_interval=30.0,
            multiplier=1.5,
        )
        
        logger.info(f"[TaskManager] 初始化: 队列={max_queue_size}, 超时={task_timeout}s")

    async def start(self) -> None:
        """启动任务处理循环"""
        if self._running:
            return
        self._running = True
        self._process_task = asyncio.create_task(self._process_loop())
        logger.info("[TaskManager] 任务处理循环已启动")

    async def stop(self) -> None:
        """停止任务处理"""
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        logger.info("[TaskManager] 任务处理循环已停止")

    async def submit_task(
        self,
        task_type: str,
        prompt: str,
        resolution: str = "720p",
        fps: int = 24,
        duration: int = 5,
        image_url: Optional[str] = None,
        last_frame_url: Optional[str] = None,
        audio_url: Optional[str] = None,
        chat_id: str = "",
        user_id: str = "",
        model_id: Optional[str] = None,
        music_enabled: bool = False,
        music_style: Optional[str] = None,
        music_volume: int = 50,
    ) -> Optional[str]:
        """提交新任务"""
        if not self._running:
            await self.start()
        
        async with self._lock:
            if len(self._task_queue) >= self._max_queue_size:
                logger.warning("[TaskManager] 队列已满")
                return None

            use_model_id = model_id or self._video_generator.get_current_model_id()

            task_id = str(uuid.uuid4())[:8]
            task = VideoTask(
                id=task_id,
                task_type=task_type,
                prompt=prompt,
                resolution=resolution,
                fps=fps,
                duration=duration,
                image_url=image_url,
                last_frame_url=last_frame_url,
                audio_url=audio_url,
                chat_id=chat_id,
                user_id=user_id,
                model_id=use_model_id,
                music_enabled=music_enabled,
                music_style=music_style,
                music_volume=music_volume,
            )
            self._task_queue.append(task)
            
            # 日志
            mode = "文生视频"
            if image_url and last_frame_url:
                mode = "首尾帧"
            elif image_url:
                mode = "首帧"
            elif last_frame_url:
                mode = "尾帧"
            
            logger.info(f"[TaskManager] 任务提交: {task_id} [{mode}]")
            return task_id

    def get_queue_position(self, task_id: str) -> int:
        """获取任务在队列中的位置"""
        for i, task in enumerate(self._task_queue):
            if task.id == task_id:
                return i + 1
        return 0

    def get_task(self, task_id: str) -> Optional[VideoTask]:
        """获取任务信息"""
        for task in self._task_queue:
            if task.id == task_id:
                return task
        if self._running_task and self._running_task.id == task_id:
            return self._running_task
        return self._completed_tasks.get(task_id)

    def get_all_status(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有任务状态"""
        running = []
        if self._running_task:
            running.append({
                "id": self._running_task.id,
                "prompt": self._running_task.prompt,
                "progress": self._running_task.progress,
                "status": self._running_task.status.value,
                "task_type": self._running_task.task_type,
                "model_id": self._running_task.model_id,
                "poll_count": self._running_task.poll_count,
            })

        queued = [
            {
                "id": task.id,
                "prompt": task.prompt,
                "status": task.status.value,
                "task_type": task.task_type,
                "model_id": task.model_id,
            }
            for task in self._task_queue
        ]

        return {"running": running, "queued": queued}

    async def cancel_task(self, task_id: str) -> Tuple[bool, str]:
        """取消任务"""
        async with self._lock:
            for i, task in enumerate(self._task_queue):
                if task.id == task_id:
                    task.status = TaskStatus.CANCELLED
                    self._task_queue.pop(i)
                    self._completed_tasks[task_id] = task
                    logger.info(f"[TaskManager] 取消排队任务: {task_id}")
                    return True, f"已取消任务 {task_id}"

            if self._running_task and self._running_task.id == task_id:
                if self._running_task.provider_task_id:
                    success, msg = await self._video_generator.cancel_task(
                        self._running_task.provider_task_id,
                        self._running_task.model_id
                    )
                    if success:
                        self._running_task.status = TaskStatus.CANCELLED
                        logger.info(f"[TaskManager] 取消运行任务: {task_id}")
                        return True, f"已取消任务 {task_id}"
                    return False, f"取消失败: {msg}"
                return False, "任务处理中，无法取消"

            return False, f"未找到任务 {task_id}"

    async def _process_loop(self) -> None:
        """任务处理循环 - 使用智能轮询"""
        while self._running:
            try:
                await self._process_next_task()
                
                # 智能轮询间隔
                if self._running_task:
                    interval = self._poller.get_interval()
                else:
                    interval = self._base_poll_interval
                    self._poller.reset()
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TaskManager] 循环异常: {e}")
                await asyncio.sleep(5)

    async def _process_next_task(self) -> None:
        """处理下一个任务"""
        if self._running_task is not None:
            await self._check_running_task()
            return

        async with self._lock:
            if not self._task_queue:
                return

            self._running_task = self._task_queue.pop(0)
            self._running_task.status = TaskStatus.RUNNING
            self._running_task.started_at = datetime.now()
            self._running_task.progress = 5
            
            # 重置轮询器
            self._poller.reset()
            
        logger.info(f"[TaskManager] 开始处理: {self._running_task.id}")
        await self._submit_to_provider(self._running_task)

    async def _submit_to_provider(self, task: VideoTask) -> None:
        """提交任务到服务商"""
        task.progress = 10
        
        try:
            success, result, model_id = await self._video_generator.generate_video(
                prompt=task.prompt,
                image_url=task.image_url,
                last_frame_url=task.last_frame_url,
                audio_url=task.audio_url,
                resolution=task.resolution,
                duration=task.duration,
                fps=task.fps,
                model_id=task.model_id,
                generate_audio=task.music_enabled,
            )

            if success:
                task.provider_task_id = result
                task.progress = 15
                logger.info(f"[TaskManager] 提交成功: {result}")
            else:
                task.status = TaskStatus.FAILED
                task.error_message = result
                logger.error(f"[TaskManager] 提交失败: {result}")
                await self._complete_task(task)
                
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            logger.error(f"[TaskManager] 提交异常: {e}")
            await self._complete_task(task)

    async def _check_running_task(self) -> None:
        """检查运行中任务 - 使用智能轮询"""
        if not self._running_task or not self._running_task.provider_task_id:
            return

        # 超时检查
        if self._running_task.started_at:
            elapsed = (datetime.now() - self._running_task.started_at).total_seconds()
            if elapsed > self._task_timeout:
                self._running_task.status = TaskStatus.TIMEOUT
                self._running_task.error_message = "任务超时"
                logger.warning(f"[TaskManager] 超时: {self._running_task.id}")
                await self._complete_task(self._running_task)
                return
            
            # 基于时间估算进度
            self._update_progress_by_time(elapsed)

        try:
            status = await self._video_generator.get_task_status(
                self._running_task.provider_task_id,
                self._running_task.model_id
            )
            
            # 更新轮询计数
            self._running_task.poll_count += 1
            
            task_status = status.get("status", "")
            provider_progress = status.get("progress", 0)

            if task_status == "succeeded":
                self._running_task.status = TaskStatus.SUCCEEDED
                self._running_task.video_url = status.get("video_url", "")
                self._running_task.progress = 100
                logger.info(f"[TaskManager] 完成: {self._running_task.id}")
                await self._complete_task(self._running_task)

            elif task_status == "failed":
                self._running_task.status = TaskStatus.FAILED
                self._running_task.error_message = status.get("message", "生成失败")
                logger.error(f"[TaskManager] 失败: {self._running_task.id}")
                await self._complete_task(self._running_task)

            elif task_status in ["running", "processing"]:
                if provider_progress > 0:
                    self._running_task.progress = min(95, max(self._running_task.progress, provider_progress))
                
                # 如果进度超过 80%，切换到快速轮询
                if self._running_task.progress >= 80:
                    self._poller.fast_poll()
                else:
                    # 正常轮询，更新间隔
                    self._poller.next()
                    
            elif task_status == "queued":
                self._running_task.progress = 10
                # 排队中，使用较长间隔
                self._poller.next()
                
            elif task_status == "cancelled":
                self._running_task.status = TaskStatus.CANCELLED
                self._running_task.error_message = "已取消"
                await self._complete_task(self._running_task)
                
            elif task_status == "error":
                self._running_task.status = TaskStatus.FAILED
                self._running_task.error_message = status.get("message", "服务商错误")
                await self._complete_task(self._running_task)
                
        except Exception as e:
            logger.error(f"[TaskManager] 查询状态失败: {e}")
            # 查询失败时增加轮询间隔
            self._poller.next()

    def _update_progress_by_time(self, elapsed_seconds: float) -> None:
        """根据时间更新进度"""
        if not self._running_task:
            return
        
        expected_duration = self._task_timeout * 0.8
        progress_ratio = min(1.0, elapsed_seconds / expected_duration)
        estimated_progress = int(15 + progress_ratio * 80)
        
        if estimated_progress > self._running_task.progress:
            self._running_task.progress = min(95, estimated_progress)

    async def _complete_task(self, task: VideoTask) -> None:
        """完成任务"""
        task.completed_at = datetime.now()
        self._completed_tasks[task.id] = task
        self._running_task = None
        
        # 重置轮询器
        self._poller.reset()
        
        logger.info(f"[TaskManager] 结束: {task.id} - {task.status.value} (轮询{task.poll_count}次)")
        await self._send_notification(task)

    async def _send_notification(self, task: VideoTask) -> None:
        """发送完成通知"""
        if not self._plugin or not task.chat_id:
            return

        try:
            # 任务类型
            if task.image_url and task.last_frame_url:
                type_text = "首尾帧图生视频"
            elif task.image_url:
                type_text = "首帧图生视频"
            elif task.last_frame_url:
                type_text = "尾帧图生视频"
            else:
                type_text = "文生视频"
            
            model_config = self._video_generator.get_model_config(task.model_id)
            model_name = model_config.get("name", task.model_id) if model_config else task.model_id
            
            if task.status == TaskStatus.SUCCEEDED:
                msg = (
                    f"🎉 {type_text}生成完成！\n"
                    f"📋 任务ID: {task.id}\n"
                    f"🎬 模型: {model_name}\n"
                    f"📝 描述: {task.prompt[:30]}...\n"
                    f"⏳ 正在下载..."
                )
                await self._plugin.send_to_chat(task.chat_id, "text", msg)
                
                if task.video_url:
                    success, result = await self._video_downloader.download(
                        task.video_url,
                        resume=True  # 启用断点续传
                    )
                    
                    if success:
                        task.local_video_path = result
                        try:
                            await self._plugin.send_to_chat(task.chat_id, "file", result)
                            logger.info(f"[TaskManager] 视频已发送")
                        except Exception as e:
                            logger.error(f"[TaskManager] 发送失败: {e}")
                            await self._plugin.send_to_chat(task.chat_id, "videourl", task.video_url)
                    else:
                        logger.warning(f"[TaskManager] 下载失败: {result}")
                        try:
                            await self._plugin.send_to_chat(task.chat_id, "videourl", task.video_url)
                        except Exception:
                            await self._plugin.send_to_chat(
                                task.chat_id, "text",
                                f"⚠️ 发送失败，请手动下载:\n{task.video_url}"
                            )
                else:
                    await self._plugin.send_to_chat(task.chat_id, "text", "⚠️ 视频URL未返回")

            elif task.status == TaskStatus.FAILED:
                await self._plugin.send_to_chat(
                    task.chat_id, "text",
                    f"❌ {type_text}生成失败\n"
                    f"📋 任务ID: {task.id}\n"
                    f"🎬 模型: {model_name}\n"
                    f"💬 原因: {task.error_message}"
                )

            elif task.status == TaskStatus.TIMEOUT:
                await self._plugin.send_to_chat(
                    task.chat_id, "text",
                    f"⏰ {type_text}生成超时\n"
                    f"📋 任务ID: {task.id}\n"
                    f"💡 请稍后重试"
                )
                
            elif task.status == TaskStatus.CANCELLED:
                await self._plugin.send_to_chat(
                    task.chat_id, "text",
                    f"🚫 任务已取消\n📋 任务ID: {task.id}"
                )
                
        except Exception as e:
            logger.error(f"[TaskManager] 通知失败: {e}")