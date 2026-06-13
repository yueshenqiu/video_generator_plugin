"""服务商基类"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple

from .capabilities import ProviderCapabilities, ModelCapabilities


class BaseProvider(ABC):
    """视频生成服务商基类"""

    PROVIDER_NAME: str = "base"
    CAPABILITIES: Optional[ProviderCapabilities] = None

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        logger: Optional[logging.Logger] = None,
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._logger = logger or logging.getLogger(f"video_generator.provider.{self.PROVIDER_NAME}")

    @classmethod
    def get_capabilities(cls) -> Optional[ProviderCapabilities]:
        return cls.CAPABILITIES
    
    @classmethod
    def get_model_capabilities(cls, model_id: str) -> Optional[ModelCapabilities]:
        if cls.CAPABILITIES:
            return cls.CAPABILITIES.get_model(model_id)
        return None

    def get_available_models(self) -> List[str]:
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
        pass

    @abstractmethod
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def cancel_task(self, task_id: str) -> Tuple[bool, str]:
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
        result = {
            "duration": duration,
            "resolution": resolution,
            "fps": fps,
            "warnings": [],
        }
        
        model_caps = self.get_model_capabilities(model)
        if not model_caps:
            return result
        
        validated_duration = model_caps.duration.validate_duration(duration)
        if validated_duration != duration:
            result["warnings"].append(f"时长已调整: {duration}s -> {validated_duration}s")
            result["duration"] = validated_duration
        
        validated_fps = model_caps.fps.validate_fps(fps)
        if validated_fps != fps:
            result["warnings"].append(f"帧率已调整: {fps} -> {validated_fps}")
            result["fps"] = validated_fps
        
        if not model_caps.resolution.supports_resolution(resolution):
            default_res = model_caps.resolution.presets[0] if model_caps.resolution.presets else "720p"
            result["warnings"].append(f"分辨率已调整: {resolution} -> {default_res}")
            result["resolution"] = default_res
        
        if has_first_frame and not model_caps.has_first_frame():
            result["warnings"].append("当前模型不支持首帧控制，将忽略首帧图片")
        
        if has_last_frame and not model_caps.has_last_frame():
            result["warnings"].append("当前模型不支持尾帧控制，将忽略尾帧图片")
        
        return result