"""阿里云 DashScope 视频生成服务商 - HTTP 实现"""

import logging
from typing import Dict, Any, Optional, Tuple

from .base import BaseProvider
from .capabilities import ALIYUN_CAPABILITIES
from ..core.http_client import AsyncHttpClient, HttpError


class AliyunProvider(BaseProvider):
    """阿里云 DashScope 视频生成服务商"""

    PROVIDER_NAME = "aliyun"
    CAPABILITIES = ALIYUN_CAPABILITIES

    ENDPOINT_CREATE = "/services/aigc/video-generation/video-synthesis"
    ENDPOINT_GET = "/tasks/{task_id}"

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(api_key, base_url, logger)
        self._base_url = base_url or "https://dashscope.aliyuncs.com/api/v1"
        self._client = AsyncHttpClient(
            base_url=self._base_url,
            api_key=api_key,
            timeout=60,
            logger=self._logger,
        )
        self._logger.info(f"[AliyunProvider] 初始化: {self._base_url}")

    def _parse_resolution(self, resolution: str) -> str:
        resolution_map = {
            "480p": "480P",
            "720p": "720P",
            "1080p": "1080P",
        }
        return resolution_map.get(resolution.lower(), resolution.upper())

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
        validated = self.validate_params(
            model=model,
            duration=duration,
            resolution=resolution,
            fps=fps,
            has_first_frame=has_first,
            has_last_frame=False,
        )
        
        for warning in validated.get("warnings", []):
            self._logger.warning(f"[AliyunProvider] {warning}")
        
        api_resolution = self._parse_resolution(validated["resolution"])
        actual_duration = validated["duration"]
        
        mode = "图生视频" if has_first else "文生视频"
        self._logger.info(f"[AliyunProvider] 创建任务: model={model}, mode={mode}")
        self._logger.debug(f"[AliyunProvider] prompt={prompt[:50]}...")

        request_body = {
            "model": model,
            "input": {
                "prompt": prompt,
            },
            "parameters": {
                "resolution": api_resolution,
                "duration": actual_duration,
                "prompt_extend": kwargs.get("prompt_extend", True),
            }
        }
        
        if has_first:
            request_body["input"]["img_url"] = image_url
            self._logger.debug("[AliyunProvider] 使用图生视频模式")
        
        if audio_url:
            request_body["input"]["audio_url"] = audio_url
            request_body["parameters"]["audio"] = True
            self._logger.debug("[AliyunProvider] 添加自定义音频")
        elif kwargs.get("generate_audio", False):
            request_body["parameters"]["audio"] = True
            self._logger.debug("[AliyunProvider] 启用自动音频生成")
        
        if "watermark" in kwargs:
            request_body["parameters"]["watermark"] = kwargs["watermark"]
        
        if kwargs.get("negative_prompt"):
            request_body["input"]["negative_prompt"] = kwargs["negative_prompt"]
        
        if kwargs.get("multi_shot") and "wan2.6" in model:
            request_body["parameters"]["shot_type"] = "multi"

        self._logger.debug(f"[AliyunProvider] 请求体: {request_body}")

        try:
            extra_headers = {"X-DashScope-Async": "enable"}
            response = await self._client.post(
                self.ENDPOINT_CREATE,
                request_body,
                extra_headers=extra_headers
            )
            
            output = response.get("output", {})
            task_id = output.get("task_id", "")
            
            if not task_id:
                raise Exception(f"未返回任务ID: {response}")
            
            self._logger.info(f"[AliyunProvider] 任务创建成功: {task_id}")
            return task_id
            
        except HttpError as e:
            self._logger.error(f"[AliyunProvider] 创建任务失败: {e}")
            raise Exception(str(e))
        except Exception as e:
            self._logger.error(f"[AliyunProvider] 创建任务异常: {e}")
            raise

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        endpoint = self.ENDPOINT_GET.format(task_id=task_id)
        
        try:
            response = await self._client.get(endpoint)
            
            output = response.get("output", {})
            status = output.get("task_status", "UNKNOWN")
            
            result = {
                "status": status.lower(),
                "progress": 0,
                "video_url": "",
                "message": ""
            }
            
            status_map = {
                "SUCCEEDED": "succeeded",
                "FAILED": "failed",
                "PENDING": "queued",
                "RUNNING": "running",
                "SUSPENDED": "running",
                "UNKNOWN": "unknown",
            }
            result["status"] = status_map.get(status, status.lower())
            
            if status == "SUCCEEDED":
                result["progress"] = 100
                result["video_url"] = output.get("video_url", "")
                self._logger.info(f"[AliyunProvider] 任务完成: {task_id}")
            elif status == "RUNNING":
                result["progress"] = 50
            elif status == "PENDING":
                result["progress"] = 10
            elif status == "FAILED":
                result["message"] = output.get("message", "生成失败")
                code = output.get("code", "")
                if code:
                    result["message"] = f"{code}: {result['message']}"
                self._logger.error(f"[AliyunProvider] 任务失败: {task_id} - {result['message']}")

            return result
            
        except HttpError as e:
            self._logger.error(f"[AliyunProvider] 查询状态失败: {e}")
            return {"status": "error", "progress": 0, "video_url": "", "message": str(e)}
        except Exception as e:
            self._logger.error(f"[AliyunProvider] 查询状态异常: {e}")
            return {"status": "error", "progress": 0, "video_url": "", "message": str(e)}

    async def cancel_task(self, task_id: str) -> Tuple[bool, str]:
        return False, "阿里云 DashScope 暂不支持取消任务"