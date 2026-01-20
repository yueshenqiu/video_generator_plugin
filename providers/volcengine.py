"""火山引擎视频生成服务商 - HTTP 实现"""

from typing import Dict, Any, Optional, Tuple

from src.common.logger import get_logger
from .base import BaseProvider
from .capabilities import VOLCENGINE_CAPABILITIES
from ..core.http_client import AsyncHttpClient, HttpError

logger = get_logger("video_generator.provider.volcengine")


class VolcengineProvider(BaseProvider):
    """火山引擎视频生成服务商"""

    PROVIDER_NAME = "volcengine"
    CAPABILITIES = VOLCENGINE_CAPABILITIES

    # API 端点
    ENDPOINT_CREATE = "/contents/generations/tasks"
    ENDPOINT_GET = "/contents/generations/tasks/{task_id}"
    ENDPOINT_DELETE = "/contents/generations/tasks/{task_id}"

    def __init__(self, api_key: str, base_url: str = ""):
        super().__init__(api_key, base_url)
        self._base_url = base_url or "https://ark.cn-beijing.volces.com/api/v3"
        self._client = AsyncHttpClient(
            base_url=self._base_url,
            api_key=api_key,
            timeout=60,  # 创建任务超时
        )
        logger.info(f"[VolcengineProvider] 初始化: {self._base_url}")

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
            logger.warning(f"[VolcengineProvider] {warning}")
        
        actual_duration = validated["duration"]
        
        # 确定模式
        if has_first and has_last:
            mode = "首尾帧图生视频"
        elif has_first:
            mode = "首帧图生视频"
        elif has_last:
            mode = "尾帧图生视频"
        else:
            mode = "文生视频"
        
        logger.info(f"[VolcengineProvider] 创建任务: model={model}, mode={mode}")
        logger.debug(f"[VolcengineProvider] prompt={prompt[:50]}...")

        # 构建 content 数组
        content = []
        
        # 获取额外参数
        watermark = kwargs.get("watermark", False)
        generate_audio = kwargs.get("generate_audio", False)
        camera_fixed = kwargs.get("camera_fixed", True)
        
        # 构建提示词（火山引擎参数放在文本中）
        prompt_parts = [prompt]
        prompt_parts.append(f"--duration {actual_duration}")
        prompt_parts.append(f"--watermark {'true' if watermark else 'false'}")
        
        # 如果是图生视频，使用自适应比例
        if has_first or has_last:
            prompt_parts.append("--ratio adaptive")
        
        # 镜头固定参数
        prompt_parts.append(f"--camerafixed {'true' if camera_fixed else 'false'}")
        
        prompt_with_params = " ".join(prompt_parts)
        
        # 1. 文本提示词
        content.append({
            "type": "text",
            "text": prompt_with_params
        })
        
        # 2. 首帧图片
        if has_first:
            first_frame_content = {
                "type": "image_url",
                "image_url": {"url": image_url}
            }
            if has_last:
                first_frame_content["role"] = "first_frame"
            content.append(first_frame_content)
            logger.debug("[VolcengineProvider] 添加首帧图片")
        
        # 3. 尾帧图片
        if has_last:
            content.append({
                "type": "image_url",
                "image_url": {"url": last_frame_url},
                "role": "last_frame"
            })
            logger.debug("[VolcengineProvider] 添加尾帧图片")

        # 构建请求体
        request_body = {
            "model": model,
            "content": content,
        }
        
        # 添加音频生成参数（仅 1.5 支持）
        if generate_audio:
            request_body["generate_audio"] = True

        logger.debug(f"[VolcengineProvider] 请求体: {request_body}")

        try:
            response = await self._client.post(self.ENDPOINT_CREATE, request_body)
            
            task_id = response.get("id", "")
            if not task_id:
                raise Exception(f"未返回任务ID: {response}")
            
            logger.info(f"[VolcengineProvider] 任务创建成功: {task_id}")
            return task_id
            
        except HttpError as e:
            logger.error(f"[VolcengineProvider] 创建任务失败: {e}")
            raise Exception(str(e))
        except Exception as e:
            logger.error(f"[VolcengineProvider] 创建任务异常: {e}")
            raise

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        
        endpoint = self.ENDPOINT_GET.format(task_id=task_id)
        
        try:
            response = await self._client.get(endpoint)
            
            status = response.get("status", "unknown")
            
            result = {
                "status": status,
                "progress": 0,
                "video_url": "",
                "message": ""
            }
            
            if status == "succeeded":
                result["progress"] = 100
                content = response.get("content", {})
                if isinstance(content, dict):
                    result["video_url"] = content.get("video_url", "")
                logger.info(f"[VolcengineProvider] 任务完成: {task_id}")
                
            elif status == "running":
                result["progress"] = 50
                
            elif status == "queued":
                result["progress"] = 10
                
            elif status == "failed":
                error = response.get("error", {})
                if isinstance(error, dict):
                    result["message"] = error.get("message", "生成失败")
                else:
                    result["message"] = str(error) if error else "生成失败"
                logger.error(f"[VolcengineProvider] 任务失败: {task_id} - {result['message']}")
                
            elif status == "cancelled":
                result["message"] = "任务已取消"
                
            elif status == "expired":
                result["status"] = "failed"
                result["message"] = "任务已过期"

            return result
            
        except HttpError as e:
            logger.error(f"[VolcengineProvider] 查询状态失败: {e}")
            return {
                "status": "error",
                "progress": 0,
                "video_url": "",
                "message": str(e)
            }
        except Exception as e:
            logger.error(f"[VolcengineProvider] 查询状态异常: {e}")
            return {
                "status": "error",
                "progress": 0,
                "video_url": "",
                "message": str(e)
            }

    async def cancel_task(self, task_id: str) -> Tuple[bool, str]:
        """取消或删除任务"""
        
        endpoint = self.ENDPOINT_DELETE.format(task_id=task_id)
        
        try:
            await self._client.delete(endpoint)
            logger.info(f"[VolcengineProvider] 任务已取消: {task_id}")
            return True, "任务已取消"
            
        except HttpError as e:
            error_msg = str(e)
            if "running" in error_msg.lower():
                return False, "运行中的任务无法取消"
            logger.error(f"[VolcengineProvider] 取消失败: {e}")
            return False, f"取消失败: {error_msg}"
        except Exception as e:
            logger.error(f"[VolcengineProvider] 取消异常: {e}")
            return False, f"取消失败: {e}"