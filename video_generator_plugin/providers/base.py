"""服务商基类"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple

from .capabilities import ProviderCapabilities, ModelCapabilities


class BaseProvider(ABC):
    """视频生成服务商基类"""

    # 子类需要定义
    PROVIDER_NAME: str = "base"
    CAPABILITIES: Optional[ProviderCapabilities] = None

    def __init__(self, api_key: str, base_url: str = ""):
        """
        初始化服务商
        
        Args:
            api_key: API密钥
            base_url: API基础URL
        """
        self._api_key = api_key
        self._base_url = base_url

    @classmethod
    def get_capabilities(cls) -> Optional[ProviderCapabilities]:
        """获取服务商能力声明"""
        return cls.CAPABILITIES
    
    @classmethod
    def get_model_capabilities(cls, model_id: str) -> Optional[ModelCapabilities]:
        """获取指定模型的能力声明"""
        if cls.CAPABILITIES:
            return cls.CAPABILITIES.get_model(model_id)
        return None

    def get_available_models(self) -> List[str]:
        """获取可用模型列表"""
        if self.CAPABILITIES:
            return self.CAPABILITIES.get_model_list()
        return []

    @abstractmethod
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
        """
        创建视频生成任务
        
        Args:
            model: 模型名称
            prompt: 提示词
            image_url: 首帧图片URL
            last_frame_url: 尾帧图片URL
            audio_url: 音频URL
            resolution: 分辨率
            duration: 时长（秒）
            fps: 帧率
            **kwargs: 其他参数
            
        Returns:
            任务ID
        """
        pass

    @abstractmethod
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            状态字典，包含:
            - status: 状态 (queued/running/succeeded/failed/cancelled)
            - progress: 进度 (0-100)
            - video_url: 视频URL（成功时）
            - message: 消息（失败时）
        """
        pass

    @abstractmethod
    async def cancel_task(self, task_id: str) -> Tuple[bool, str]:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            (是否成功, 消息)
        """
        pass
    
    def validate_params(
        self,
        model: str,
        duration: int,
        resolution: str,
        fps: int,
        has_first_frame: bool = False,
        has_last_frame: bool = False,
    ) -> Dict[str, Any]:
        """
        验证并调整参数
        
        Args:
            model: 模型名称
            duration: 时长
            resolution: 分辨率
            fps: 帧率
            has_first_frame: 是否有首帧
            has_last_frame: 是否有尾帧
            
        Returns:
            调整后的参数字典
        """
        result = {
            "duration": duration,
            "resolution": resolution,
            "fps": fps,
            "warnings": [],
        }
        
        model_caps = self.get_model_capabilities(model)
        if not model_caps:
            return result
        
        # 验证时长
        validated_duration = model_caps.duration.validate_duration(duration)
        if validated_duration != duration:
            result["warnings"].append(f"时长已调整: {duration}s -> {validated_duration}s")
            result["duration"] = validated_duration
        
        # 验证帧率
        validated_fps = model_caps.fps.validate_fps(fps)
        if validated_fps != fps:
            result["warnings"].append(f"帧率已调整: {fps} -> {validated_fps}")
            result["fps"] = validated_fps
        
        # 验证分辨率
        if not model_caps.resolution.supports_resolution(resolution):
            default_res = model_caps.resolution.presets[0] if model_caps.resolution.presets else "720p"
            result["warnings"].append(f"分辨率已调整: {resolution} -> {default_res}")
            result["resolution"] = default_res
        
        # 验证首尾帧支持
        if has_first_frame and not model_caps.has_first_frame():
            result["warnings"].append("当前模型不支持首帧控制，将忽略首帧图片")
        
        if has_last_frame and not model_caps.has_last_frame():
            result["warnings"].append("当前模型不支持尾帧控制，将忽略尾帧图片")
        
        return result