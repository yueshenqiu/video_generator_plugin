"""OpenAI 兼容接口服务商 - 用于中转站等兼容服务"""

from typing import Dict, Any, Optional, Tuple

from src.common.logger import get_logger
from .base import BaseProvider
from .capabilities import OPENAI_CAPABILITIES, ModelCapabilities, VideoFeature
from ..core.http_client import AsyncHttpClient, HttpError

logger = get_logger("video_generator.provider.openai")


class OpenAICompatibleProvider(BaseProvider):
    """
    OpenAI 兼容格式服务商
    
    支持任何兼容 OpenAI API 格式的服务：
    - 各类中转站
    - 本地部署服务
    - 其他兼容 OpenAI 格式的 API
    
    注意：由于不同服务的实现差异，部分功能可能不可用
    """

    PROVIDER_NAME = "openai"
    CAPABILITIES = OPENAI_CAPABILITIES

    def __init__(self, api_key: str, base_url: str = ""):
        super().__init__(api_key, base_url)
        self._base_url = base_url or "https://api.openai.com/v1"
        self._client = AsyncHttpClient(
            base_url=self._base_url,
            api_key=api_key,
            timeout=60,
        )
        logger.info(f"[OpenAIProvider] 初始化: {self._base_url}")

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
        """创建视频生成任务"""
        
        has_first = bool(image_url)
        has_last = bool(last_frame_url)
        
        # 确定模式
        if has_first and has_last:
            mode = "首尾帧图生视频"
        elif has_first:
            mode = "图生视频"
        else:
            mode = "文生视频"
        
        logger.info(f"[OpenAIProvider] 创建任务: model={model}, mode={mode}")
        logger.debug(f"[OpenAIProvider] prompt={prompt[:50]}...")

        # 构建请求体 - 尝试多种可能的格式
        # 格式1：类似 ChatCompletion 的 messages 格式
        content = [{"type": "text", "text": prompt}]
        
        if has_first:
            content.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })
        
        if has_last:
            content.append({
                "type": "image_url",
                "image_url": {"url": last_frame_url}
            })

        # 尝试不同的请求格式
        request_body = {
            "model": model,
            "prompt": prompt,
        }
        
        # 添加图片（如果有）
        if has_first:
            request_body["image"] = image_url
            if has_last:
                request_body["image"] = [image_url, last_frame_url]
        
        # 添加视频参数
        request_body["duration"] = duration
        request_body["resolution"] = resolution
        request_body["fps"] = fps
        
        # 添加额外参数
        for key in ["size", "quality", "style"]:
            if key in kwargs:
                request_body[key] = kwargs[key]

        logger.debug(f"[OpenAIProvider] 请求体: {request_body}")

        # 尝试多个可能的端点
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
                
                # 尝试从不同格式的响应中获取任务ID
                task_id = (
                    response.get("id") or
                    response.get("task_id") or
                    response.get("data", {}).get("id") or
                    response.get("data", {}).get("task_id") or
                    ""
                )
                
                if task_id:
                    logger.info(f"[OpenAIProvider] 任务创建成功: {task_id}")
                    return task_id
                
                # 如果是同步返回视频的情况
                video_url = (
                    response.get("video_url") or
                    response.get("url") or
                    response.get("data", {}).get("url") or
                    ""
                )
                if video_url:
                    # 同步返回，创建伪任务ID
                    self._sync_result = {"video_url": video_url}
                    return f"sync_{hash(video_url) & 0xFFFFFFFF:08x}"
                
                logger.warning(f"[OpenAIProvider] 端点 {endpoint} 响应无任务ID: {response}")
                
            except HttpError as e:
                last_error = e
                if e.status_code == 404:
                    continue  # 尝试下一个端点
                raise Exception(str(e))
            except Exception as e:
                last_error = e
                continue
        
        # 所有端点都失败
        error_msg = f"所有端点都失败: {last_error}"
        logger.error(f"[OpenAIProvider] {error_msg}")
        raise Exception(error_msg)

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        
        # 处理同步返回的情况
        if task_id.startswith("sync_") and hasattr(self, "_sync_result"):
            return {
                "status": "succeeded",
                "progress": 100,
                "video_url": self._sync_result.get("video_url", ""),
                "message": ""
            }
        
        # 尝试多个可能的端点
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
                
                # 尝试解析不同格式的响应
                status = (
                    response.get("status") or
                    response.get("task_status") or
                    response.get("state") or
                    "unknown"
                )
                
                # 状态标准化
                status_lower = status.lower()
                if status_lower in ["success", "succeeded", "completed", "done"]:
                    status = "succeeded"
                elif status_lower in ["processing", "running", "pending", "in_progress"]:
                    status = "running"
                elif status_lower in ["failed", "error", "fail"]:
                    status = "failed"
                elif status_lower in ["queued", "waiting"]:
                    status = "queued"
                
                # 获取视频URL
                video_url = (
                    response.get("video_url") or
                    response.get("url") or
                    response.get("result", {}).get("url") or
                    response.get("data", {}).get("url") or
                    response.get("output", {}).get("video_url") or
                    ""
                )
                
                # 获取进度
                progress = response.get("progress", 0)
                if status == "succeeded":
                    progress = 100
                elif status == "running" and progress == 0:
                    progress = 50
                elif status == "queued":
                    progress = 10
                
                # 获取错误信息
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
                return {
                    "status": "error",
                    "progress": 0,
                    "video_url": "",
                    "message": str(e)
                }
            except Exception:
                continue
        
        return {
            "status": "error",
            "progress": 0,
            "video_url": "",
            "message": "无法获取任务状态"
        }

    async def cancel_task(self, task_id: str) -> Tuple[bool, str]:
        """取消任务"""
        
        # 同步任务无法取消
        if task_id.startswith("sync_"):
            return False, "同步任务无法取消"
        
        # 尝试多个可能的端点
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