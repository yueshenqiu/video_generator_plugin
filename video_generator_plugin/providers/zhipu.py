"""智谱 CogVideoX 视频生成服务商"""

from typing import Dict, Any, Optional, Tuple, List, Union

from src.common.logger import get_logger
from .base import BaseProvider
from .capabilities import ZHIPU_CAPABILITIES
from ..core.http_client import AsyncHttpClient, HttpError

logger = get_logger("video_generator.provider.zhipu")


class ZhipuProvider(BaseProvider):
    """智谱 CogVideoX 视频生成服务商"""

    PROVIDER_NAME = "zhipu"
    CAPABILITIES = ZHIPU_CAPABILITIES

    # API 端点
    ENDPOINT_CREATE = "/paas/v4/videos/generations"
    ENDPOINT_GET = "/paas/v4/async-result/{task_id}"

    # 分辨率映射
    RESOLUTION_MAP = {
        "720p": "1280x720",
        "1080p": "1920x1080",
        "4k": "3840x2160",
    }

    def __init__(self, api_key: str, base_url: str = ""):
        super().__init__(api_key, base_url)
        self._base_url = base_url or "https://open.bigmodel.cn/api"
        self._client = AsyncHttpClient(
            base_url=self._base_url,
            api_key=api_key,
            timeout=60,
        )
        logger.info(f"[ZhipuProvider] 初始化: {self._base_url}")

    def _parse_resolution(self, resolution: str) -> str:
        """解析分辨率为智谱格式"""
        return self.RESOLUTION_MAP.get(resolution.lower(), "1920x1080")

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
        has_last = bool(last_frame_url)
        validated = self.validate_params(
            model=model,
            duration=duration,
            resolution=resolution,
            fps=fps,
            has_first_frame=has_first,
            has_last_frame=has_last,
        )
        
        for warning in validated.get("warnings", []):
            logger.warning(f"[ZhipuProvider] {warning}")
        
        api_resolution = self._parse_resolution(validated["resolution"])
        actual_duration = validated["duration"]
        actual_fps = validated["fps"]
        
        # 确定模式
        if has_first and has_last:
            mode = "首尾帧图生视频"
        elif has_first:
            mode = "图生视频"
        else:
            mode = "文生视频"
        
        logger.info(f"[ZhipuProvider] 创建任务: model={model}, mode={mode}")
        logger.debug(f"[ZhipuProvider] prompt={prompt[:50]}...")

        # 构建请求体
        request_body = {
            "model": model,
            "prompt": prompt,
            "size": api_resolution,
            "fps": actual_fps,
            "duration": actual_duration,
            "with_audio": kwargs.get("with_audio", False),
            "quality": kwargs.get("quality", "speed"),  # speed 或 quality
        }
        
        # 处理图片输入
        # 智谱的 image_url 可以是字符串（单张）或数组（首尾帧）
        if has_first and has_last:
            # 首尾帧模式：传入数组
            request_body["image_url"] = [image_url, last_frame_url]
            logger.debug("[ZhipuProvider] 使用首尾帧模式")
        elif has_first:
            # 单图模式：传入字符串
            request_body["image_url"] = image_url
            logger.debug("[ZhipuProvider] 使用图生视频模式")
        
        # 水印控制
        if "watermark" in kwargs:
            request_body["watermark_enabled"] = kwargs["watermark"]
        
        # 用户追踪ID（可选）
        if kwargs.get("user_id"):
            request_body["user_id"] = kwargs["user_id"]
        
        # 请求ID（可选）
        if kwargs.get("request_id"):
            request_body["request_id"] = kwargs["request_id"]

        logger.debug(f"[ZhipuProvider] 请求体: {request_body}")

        try:
            response = await self._client.post(self.ENDPOINT_CREATE, request_body)
            
            task_id = response.get("id", "")
            if not task_id:
                raise Exception(f"未返回任务ID: {response}")
            
            task_status = response.get("task_status", "")
            logger.info(f"[ZhipuProvider] 任务创建成功: {task_id}, 状态: {task_status}")
            return task_id
            
        except HttpError as e:
            logger.error(f"[ZhipuProvider] 创建任务失败: {e}")
            raise Exception(str(e))
        except Exception as e:
            logger.error(f"[ZhipuProvider] 创建任务异常: {e}")
            raise

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        
        endpoint = self.ENDPOINT_GET.format(task_id=task_id)
        
        try:
            response = await self._client.get(endpoint)
            
            status = response.get("task_status", "UNKNOWN")
            
            result = {
                "status": status.lower(),
                "progress": 0,
                "video_url": "",
                "message": ""
            }
            
            # 状态映射
            status_map = {
                "SUCCESS": "succeeded",
                "PROCESSING": "running",
                "FAIL": "failed",
            }
            result["status"] = status_map.get(status, status.lower())
            
            if status == "SUCCESS":
                result["progress"] = 100
                # 智谱的视频结果
                video_result = response.get("video_result", [])
                if video_result and isinstance(video_result, list) and len(video_result) > 0:
                    result["video_url"] = video_result[0].get("url", "")
                logger.info(f"[ZhipuProvider] 任务完成: {task_id}")
                
            elif status == "PROCESSING":
                result["progress"] = 50
                
            elif status == "FAIL":
                result["message"] = response.get("message", "生成失败")
                logger.error(f"[ZhipuProvider] 任务失败: {task_id} - {result['message']}")

            return result
            
        except HttpError as e:
            logger.error(f"[ZhipuProvider] 查询状态失败: {e}")
            return {
                "status": "error",
                "progress": 0,
                "video_url": "",
                "message": str(e)
            }
        except Exception as e:
            logger.error(f"[ZhipuProvider] 查询状态异常: {e}")
            return {
                "status": "error",
                "progress": 0,
                "video_url": "",
                "message": str(e)
            }

    async def cancel_task(self, task_id: str) -> Tuple[bool, str]:
        """取消任务（智谱暂不支持）"""
        return False, "智谱 CogVideoX 暂不支持取消任务"