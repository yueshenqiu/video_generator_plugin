"""任务管理模块 - 支持任务队列、轮询、回调通知"""

import asyncio
import uuid
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable, Tuple, Set


class TaskStatus(Enum):
    """任务状态枚举"""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class VideoTask:
    """视频生成任务"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    task_type: str = "text2video"  # text2video / image2video
    status: TaskStatus = TaskStatus.QUEUED
    prompt: str = ""
    resolution: str = "720p"
    fps: int = 24
    duration: int = 5
    image_url: Optional[str] = None
    last_frame_url: Optional[str] = None
    chat_id: str = ""
    user_id: str = ""
    model_id: str = ""
    video_url: Optional[str] = None
    local_video_path: Optional[str] = None
    error_message: str = ""
    progress: int = 0
    poll_count: int = 0
    created_at: float = field(default_factory=lambda: __import__('time').time())
    music_enabled: bool = False
    music_style: Optional[str] = None
    music_volume: int = 50


class TaskManager:
    """任务管理器 - 支持队列、并发控制、轮询和回调通知"""

    def __init__(
        self,
        video_generator,
        max_queue_size: int = 10,
        task_timeout: int = 600,
        poll_interval: int = 5,
        send_callback: Optional[Callable] = None,
        video_downloader=None,
        logger: Optional[logging.Logger] = None,
    ):
        self._logger = logger or logging.getLogger("video_generator.task_manager")
        self._video_generator = video_generator
        self._video_downloader = video_downloader
        self._max_queue_size = max_queue_size
        self._task_timeout = task_timeout
        self._poll_interval = poll_interval
        self._send_to_chat = send_callback or (lambda c, t, m: None)

        # 任务存储
        self._tasks: Dict[str, VideoTask] = {}
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._running_tasks: Set[str] = set()
        self._completed_task_ids: Set[str] = set()

        # 控制
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

        self._logger.info(f"[TaskManager] 初始化: max_queue={max_queue_size}, timeout={task_timeout}s")

    # ==================== 生命周期 ====================

    def start(self):
        """启动任务管理器"""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._worker_task = asyncio.create_task(self._worker_loop())
        self._logger.info("[TaskManager] 已启动")

    async def stop(self):
        """停止任务管理器"""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

        self._logger.info("[TaskManager] 已停止")

    # ==================== 任务提交 ====================

    async def submit_task(
        self,
        task_type: str,
        prompt: str,
        resolution: str = "720p",
        fps: int = 24,
        duration: int = 5,
        image_url: Optional[str] = None,
        last_frame_url: Optional[str] = None,
        chat_id: str = "",
        user_id: str = "",
        music_enabled: bool = False,
        music_style: Optional[str] = None,
        music_volume: int = 50,
    ) -> Optional[str]:
        """提交视频生成任务"""
        # 获取当前模型
        model_id = self._video_generator.get_current_model_id()

        task = VideoTask(
            task_type=task_type,
            prompt=prompt,
            resolution=resolution,
            fps=fps,
            duration=duration,
            image_url=image_url,
            last_frame_url=last_frame_url,
            chat_id=chat_id,
            user_id=user_id,
            model_id=model_id,
            music_enabled=music_enabled,
            music_style=music_style,
            music_volume=music_volume,
        )

        try:
            self._queue.put_nowait(task.id)
            self._tasks[task.id] = task
            self._logger.info(f"[TaskManager] 任务已提交: {task.id}, type={task_type}")

            # 确保 worker 在运行
            if not self._running:
                self.start()

            return task.id

        except asyncio.QueueFull:
            self._logger.warning("[TaskManager] 队列已满，拒绝新任务")
            return None

    async def cancel_task(self, task_id: str) -> Tuple[bool, str]:
        """取消任务"""
        task = self._tasks.get(task_id)
        if not task:
            return False, f"任务 {task_id} 不存在"

        if task.status == TaskStatus.SUCCEEDED:
            return False, "任务已完成，无法取消"

        if task.status == TaskStatus.FAILED:
            return False, "任务已失败，无法取消"

        task.status = TaskStatus.CANCELLED

        # 尝试调用服务商取消
        try:
            await self._video_generator.cancel_task(task_id, task.model_id)
        except Exception as e:
            self._logger.debug(f"[TaskManager] 远端取消失败（可忽略）: {e}")

        self._completed_task_ids.add(task_id)
        self._logger.info(f"[TaskManager] 任务已取消: {task_id}")
        return True, f"任务 {task_id} 已取消"

    # ==================== 任务查询 ====================

    def get_task(self, task_id: str) -> Optional[VideoTask]:
        return self._tasks.get(task_id)

    def get_queue_position(self, task_id: str) -> int:
        """获取任务在队列中的位置（0表示正在执行）"""
        if task_id in self._running_tasks:
            return 0
        position = 1
        for qid in list(self._queue._queue):
            if qid == task_id:
                return position
            position += 1
        return -1

    def get_all_status(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有任务状态"""
        running_list = []
        queued_list = []

        for task_id in self._running_tasks:
            task = self._tasks.get(task_id)
            if task:
                running_list.append({
                    "id": task.id,
                    "task_type": task.task_type,
                    "status": task.status.value,
                    "prompt": task.prompt,
                    "progress": task.progress,
                    "poll_count": task.poll_count,
                })

        for qid in list(self._queue._queue):
            task = self._tasks.get(qid)
            if task and task.status == TaskStatus.QUEUED:
                queued_list.append({
                    "id": task.id,
                    "task_type": task.task_type,
                    "prompt": task.prompt,
                })

        return {"running": running_list, "queued": queued_list}

    # ==================== 工作循环 ====================

    async def _worker_loop(self):
        """主工作循环 - 从队列取任务并处理"""
        self._logger.info("[TaskManager] 工作循环已启动")

        while self._running:
            try:
                # 等待新任务（带超时以便检查停止信号）
                try:
                    task_id = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    continue

                task = self._tasks.get(task_id)
                if not task:
                    continue

                if task.status == TaskStatus.CANCELLED:
                    self._queue.task_done()
                    continue

                # 执行任务
                self._running_tasks.add(task_id)
                task.status = TaskStatus.RUNNING

                await self._execute_task(task)

                self._running_tasks.discard(task_id)
                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"[TaskManager] 工作循环异常: {e}")

        self._logger.info("[TaskManager] 工作循环已结束")

    async def _execute_task(self, task: VideoTask):
        """执行单个任务"""
        self._logger.info(f"[TaskManager] 开始执行任务: {task.id}")

        # 提交生成任务
        success, result, model_id = await self._video_generator.generate_video(
            prompt=task.prompt,
            image_url=task.image_url,
            last_frame_url=task.last_frame_url,
            resolution=task.resolution,
            duration=task.duration,
            fps=task.fps,
            model_id=task.model_id,
        )

        if not success:
            task.status = TaskStatus.FAILED
            task.error_message = result
            task.poll_count += 1
            self._completed_task_ids.add(task.id)
            await self._send_notification(task)
            return

        task.model_id = model_id
        remote_task_id = result
        self._logger.info(f"[TaskManager] 远程任务已提交: {remote_task_id}")

        # 轮询任务状态
        poll_interval = self._poll_interval
        max_polls = max(1, self._task_timeout // poll_interval)
        start_time = asyncio.get_event_loop().time()

        for poll_count in range(max_polls):
            # 检查是否被取消
            if task.status == TaskStatus.CANCELLED:
                return

            # 检查是否超时
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > self._task_timeout:
                task.status = TaskStatus.TIMEOUT
                task.error_message = f"生成超时 ({self._task_timeout}秒)"
                self._completed_task_ids.add(task.id)
                await self._send_notification(task)
                return

            # 等待轮询间隔
            await asyncio.sleep(poll_interval)

            try:
                status_data = await self._video_generator.get_task_status(
                    remote_task_id, model_id
                )

                api_status = status_data.get("status", "unknown")
                task.progress = status_data.get("progress", task.progress)
                task.poll_count = poll_count + 1

                self._logger.debug(
                    f"[TaskManager] 任务 {task.id} 状态: {api_status}, "
                    f"进度: {task.progress}%"
                )

                if api_status == "succeeded":
                    task.status = TaskStatus.SUCCEEDED
                    task.video_url = status_data.get("video_url", "")
                    self._completed_task_ids.add(task.id)
                    await self._send_notification(task)
                    return

                elif api_status == "failed":
                    task.status = TaskStatus.FAILED
                    task.error_message = status_data.get("message", "生成失败")
                    self._completed_task_ids.add(task.id)
                    await self._send_notification(task)
                    return

            except Exception as e:
                self._logger.error(f"[TaskManager] 轮询异常: {e}")

        # 轮询耗尽
        task.status = TaskStatus.TIMEOUT
        task.error_message = f"轮询次数耗尽 ({max_polls}次)"
        self._completed_task_ids.add(task.id)
        await self._send_notification(task)

    # ==================== 通知 ====================

    async def _send_notification(self, task: VideoTask) -> None:
        """发送完成通知"""
        if not task.chat_id:
            return

        try:
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
                await self._send_to_chat(task.chat_id, "text", msg)

                if task.video_url:
                    success = False
                    result = ""

                    if self._video_downloader:
                        success, result = await self._video_downloader.download(
                            task.video_url,
                            resume=True,
                        )

                    if success:
                        task.local_video_path = result
                        try:
                            await self._send_to_chat(task.chat_id, "file", result)
                            self._logger.info("[TaskManager] 视频已发送")
                        except Exception as e:
                            self._logger.error(f"[TaskManager] 发送失败: {e}")
                            await self._send_to_chat(task.chat_id, "videourl", task.video_url)
                    else:
                        self._logger.warning("[TaskManager] 下载失败，发送视频链接")
                        try:
                            await self._send_to_chat(task.chat_id, "videourl", task.video_url)
                        except Exception:
                            await self._send_to_chat(
                                task.chat_id, "text",
                                f"⚠️ 发送失败，请手动下载:\n{task.video_url}"
                            )
                else:
                    await self._send_to_chat(task.chat_id, "text", "⚠️ 视频URL未返回")

            elif task.status == TaskStatus.FAILED:
                await self._send_to_chat(
                    task.chat_id, "text",
                    f"❌ {type_text}生成失败\n"
                    f"📋 任务ID: {task.id}\n"
                    f"🎬 模型: {model_name}\n"
                    f"💬 原因: {task.error_message}"
                )

            elif task.status == TaskStatus.TIMEOUT:
                await self._send_to_chat(
                    task.chat_id, "text",
                    f"⏰ {type_text}生成超时\n"
                    f"📋 任务ID: {task.id}\n"
                    f"💡 请稍后重试"
                )

            elif task.status == TaskStatus.CANCELLED:
                await self._send_to_chat(
                    task.chat_id, "text",
                    f"🚫 任务已取消\n📋 任务ID: {task.id}"
                )

        except Exception as e:
            self._logger.error(f"[TaskManager] 通知失败: {e}")
