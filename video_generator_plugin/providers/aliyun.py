"""阿里云 DashScope 视频生成服务商 - HTTP 实现"""

from typing import Dict, Any, Optional, Tuple

from src.common.logger import get_logger
from .base import BaseProvider
from .capabilities import ALIYUN_CAPABILITIES
from ..core.http_client import AsyncHttpClient, HttpError

logger = get_logger("video_generator.provider.aliyun")


class AliyunProvider(BaseProvider):
    """阿里云 DashScope 视频生成服务商"""

    PROVIDER_NAME = "aliyun"
    CAPABILITIES = ALIYUN_CAPABILITIES

    # API 端点
    ENDPOINT_CREATE = "/services/aigc/video-generation/video-synthesis"
    ENDPOINT_GET = "/tasks/{task_id}"

    def __init__(self, api_key: str, base_url: str = ""):
        super().__init__(api_key, base_url)
        self._base_url = base_url or "https://dashscope.aliyuncs.com/api/v1"
        self._client = AsyncHttpClient(
            base_url=self._base_url,
            api_key=api_key,
            timeout=60,
        )
        logger.info(f"[AliyunProvider] 初始化: {self._base_url}")

    def _parse_resolution(self, resolution: str) -> str:
        """解析分辨率为阿里云格式"""
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
        """创建视频生成任务"""
        
        # 验证参数
        has_first = bool(image_url)
        validated = self.validate_params(
            model=model,
            duration=duration,
            resolution=resolution,
            fps=fps,
            has_first_frame=has_first,
            has_last_frame=False,  # 阿里云暂不支持尾帧
        )
        
        for warning in validated.get("warnings", []):
            logger.warning(f"[AliyunProvider] {warning}")
        
        api_resolution = self._parse_resolution(validated["resolution"])
        actual_duration = validated["duration"]
        
        # 确定模式
        mode = "图生视频" if has_first else "文生视频"
        logger.info(f"[AliyunProvider] 创建任务: model={model}, mode={mode}")
        logger.debug(f"[AliyunProvider] prompt={prompt[:50]}...")

        # 构建请求体
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
        
        # 图生视频
        if has_first:
            request_body["input"]["img_url"] = image_url
            logger.debug("[AliyunProvider] 使用图生视频模式")
        
        # 音频
        if audio_url:
            request_body["input"]["audio_url"] = audio_url
            logger.debug("[AliyunProvider] 添加自定义音频")
        
        # 水印
        if "watermark" in kwargs:
            request_body["parameters"]["watermark"] = kwargs["watermark"]
        
        # 负向提示词
        if kwargs.get("negative_prompt"):
            request_body["input"]["negative_prompt"] = kwargs["negative_prompt"]
        
        # 多镜头叙事（wan2.6 支持）
        if kwargs.get("multi_shot") and "wan2.6" in model:
            request_body["parameters"]["shot_type"] = "multi"

        logger.debug(f"[AliyunProvider] 请求体: {request_body}")

        try:
            # 阿里云需要特殊请求头来启用异步
            extra_headers = {"X-DashScope-Async": "enable"}
            response = await self._client.post(
                self.ENDPOINT_CREATE, 
                request_body,
                extra_headers=extra_headers
            )
            
            # 阿里云响应格式
            output = response.get("output", {})
            task_id = output.get("task_id", "")
            
            if not task_id:
                raise Exception(f"未返回任务ID: {response}")
            
            logger.info(f"[AliyunProvider] 任务创建成功: {task_id}")
            return task_id
            
        except HttpError as e:
            logger.error(f"[AliyunProvider] 创建任务失败: {e}")
            raise Exception(str(e))
        except Exception as e:
            logger.error(f"[AliyunProvider] 创建任务异常: {e}")
            raise

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        
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
            
            # 状态映射
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
                logger.info(f"[AliyunProvider] 任务完成: {task_id}")
                
            elif status == "RUNNING":
                result["progress"] = 50
                
            elif status == "PENDING":
                result["progress"] = 10
                
            elif status == "FAILED":
                result["message"] = output.get("message", "生成失败")
                # 尝试从 code 获取更多信息
                code = output.get("code", "")
                if code:
                    result["message"] = f"{code}: {result['message']}"
                logger.error(f"[AliyunProvider] 任务失败: {task_id} - {result['message']}")

            return result
            
        except HttpError as e:
            logger.error(f"[AliyunProvider] 查询状态失败: {e}")
            return {
                "status": "error",
                "progress": 0,
                "video_url": "",
                "message": str(e)
            }
        except Exception as e:
            logger.error(f"[AliyunProvider] 查询状态异常: {e}")
            return {
                "status": "error",
                "progress": 0,
                "video_url": "",
                "message": str(e)
            }

    async def cancel_task(self, task_id: str) -> Tuple[bool, str]:
        """取消任务（阿里云暂不支持）"""
        return False, "阿里云 DashScope 暂不支持取消任务"