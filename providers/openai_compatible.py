"""OpenAI 兼容接口服务商 - 用于中转站等兼容服务"""

import logging
from typing import Dict, Any, Optional, Tuple

from .base import BaseProvider
from .capabilities import OPENAI_CAPABILITIES
from ..core.http_client import AsyncHttpClient, HttpError


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI 兼容格式服务商"""

    PROVIDER_NAME = "openai"
    CAPABILITIES = OPENAI_CAPABILITIES

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(api_key, base_url, logger)
        self._base_url = base_url or "https://api.openai.com/v1"
        self._client = AsyncHttpClient(
            base_url=self._base_url,
            api_key=api_key,
            timeout=60,
            logger=self._logger,
        )
        self._logger.info(f"[OpenAIProvider] 初始化: {self._base_url}")

    async def create_task(
        self,
        model: str,
        prompt: str,
        image_url: Optional[str] = None,
        last_frame_url: Optional[str] = None,
        audio_url: Optional[str] = None,
        resolution: str = "720p",
        duration: int = 5,
        fps: int = 24,
        **kwargs
    ) -> str:
        has_first = bool(image_url)
        has_last = bool(last_frame_url)
        
        if has_first and has_last:
            mode = "首尾帧图生视频"
        elif has_first:
            mode = "图生视频"
        else:
            mode = "文生视频"
        
        self._logger.info(f"[OpenAIProvider] 创建任务: model={model}, mode={mode}")
        self._logger.debug(f"[OpenAIProvider] prompt={prompt[:50]}...")

        request_body = {
            "model": model,
            "prompt": prompt,
        }
        
        if has_first:
            request_body["image"] = image_url
            if has_last:
                request_body["image"] = [image_url, last_frame_url]
        
        request_body["duration"] = duration
        request_body["resolution"] = resolution
        request_body["fps"] = fps
        
        for key in ["size", "quality", "style"]:
            if key in kwargs:
                request_body[key] = kwargs[key]

        self._logger.debug(f"[OpenAIProvider] 请求体: {request_body}")

        endpoints = [
            "/video/generations",
            "/videos/generations",
            "/v1/video/generations",
            "/generations/video",
        ]
        
        last_error = None
        for endpoint in endpoints:
            try:
                response = await self._client.post(endpoint, request_body)
                
                task_id = (
                    response.get("id") or
                    response.get("task_id") or
                    response.get("data", {}).get("id") or
                    response.get("data", {}).get("task_id") or
                    ""
                )
                
                if task_id:
                    self._logger.info(f"[OpenAIProvider] 任务创建成功: {task_id}")
                    return task_id
                
                video_url = (
                    response.get("video_url") or
                    response.get("url") or
                    response.get("data", {}).get("url") or
                    ""
                )
                if video_url:
                    self._sync_result = {"video_url": video_url}
                    return f"sync_{hash(video_url) & 0xFFFFFFFF:08x}"
                
                self._logger.warning(f"[OpenAIProvider] 端点 {endpoint} 响应无任务ID: {response}")
                
            except HttpError as e:
                last_error = e
                if e.status_code == 404:
                    continue
                raise Exception(str(e))
            except Exception as e:
                last_error = e
                continue
        
        error_msg = f"所有端点都失败: {last_error}"
        self._logger.error(f"[OpenAIProvider] {error_msg}")
        raise Exception(error_msg)

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        if task_id.startswith("sync_") and hasattr(self, "_sync_result"):
            return {
                "status": "succeeded",
                "progress": 100,
                "video_url": self._sync_result.get("video_url", ""),
                "message": ""
            }
        
        endpoints = [
            f"/video/generations/{task_id}",
            f"/videos/generations/{task_id}",
            f"/v1/video/generations/{task_id}",
            f"/tasks/{task_id}",
            f"/async-result/{task_id}",
        ]
        
        for endpoint in endpoints:
            try:
                response = await self._client.get(endpoint)
                
                status = (
                    response.get("status") or
                    response.get("task_status") or
                    response.get("state") or
                    "unknown"
                )
                
                status_lower = status.lower()
                if status_lower in ["success", "succeeded", "completed", "done"]:
                    status = "succeeded"
                elif status_lower in ["processing", "running", "pending", "in_progress"]:
                    status = "running"
                elif status_lower in ["failed", "error", "fail"]:
                    status = "failed"
                elif status_lower in ["queued", "waiting"]:
                    status = "queued"
                
                video_url = (
                    response.get("video_url") or
                    response.get("url") or
                    response.get("result", {}).get("url") or
                    response.get("data", {}).get("url") or
                    response.get("output", {}).get("video_url") or
                    ""
                )
                
                progress = response.get("progress", 0)
                if status == "succeeded":
                    progress = 100
                elif status == "running" and progress == 0:
                    progress = 50
                elif status == "queued":
                    progress = 10
                
                message = (
                    response.get("message") or
                    response.get("error", {}).get("message") or
                    response.get("error_message") or
                    ""
                )
                
                return {
                    "status": status,
                    "progress": progress,
                    "video_url": video_url,
                    "message": message
                }
                
            except HttpError as e:
                if e.status_code == 404:
                    continue
                return {"status": "error", "progress": 0, "video_url": "", "message": str(e)}
            except Exception:
                continue
        
        return {"status": "error", "progress": 0, "video_url": "", "message": "无法获取任务状态"}

    async def cancel_task(self, task_id: str) -> Tuple[bool, str]:
        if task_id.startswith("sync_"):
            return False, "同步任务无法取消"
        
        endpoints = [
            f"/video/generations/{task_id}",
            f"/videos/generations/{task_id}/cancel",
            f"/tasks/{task_id}/cancel",
        ]
        
        for endpoint in endpoints:
            try:
                if "cancel" in endpoint:
                    await self._client.post(endpoint, {})
                else:
                    await self._client.delete(endpoint)
                return True, "任务已取消"
            except HttpError as e:
                if e.status_code == 404:
                    continue
                return False, str(e)
            except Exception:
                continue
        
        return False, "取消失败：接口不支持"