"""分辨率校验模块"""

import re
from typing import Tuple, Optional


class ResolutionValidator:
    """分辨率校验器"""

    MIN_SIZE = 200
    MAX_SIZE = 4096

    PRESET_RESOLUTIONS = {
        "720p": (1280, 720),
        "1080p": (1920, 1080),
        "480p": (854, 480),
        "4k": (3840, 2160),
    }

    VALID_FPS = [15, 24, 30]
    MIN_DURATION = 1
    MAX_DURATION = 30

    @classmethod
    def is_custom_resolution(cls, resolution: str) -> bool:
        """判断是否为自定义分辨率"""
        return bool(re.match(r"^\d+x\d+$", resolution, re.IGNORECASE))

    @classmethod
    def parse_resolution(cls, resolution: str) -> Optional[Tuple[int, int]]:
        """解析分辨率"""
        resolution = resolution.lower().strip()

        if resolution in cls.PRESET_RESOLUTIONS:
            return cls.PRESET_RESOLUTIONS[resolution]

        if cls.is_custom_resolution(resolution):
            parts = resolution.split("x")
            try:
                return (int(parts[0]), int(parts[1]))
            except ValueError:
                return None

        return None

    @classmethod
    def validate_custom_resolution(cls, resolution: str) -> bool:
        """验证自定义分辨率"""
        parsed = cls.parse_resolution(resolution)
        if parsed is None:
            return False

        width, height = parsed
        return (cls.MIN_SIZE <= width <= cls.MAX_SIZE and 
                cls.MIN_SIZE <= height <= cls.MAX_SIZE)

    @classmethod
    def is_valid_fps(cls, fps: int) -> bool:
        """验证帧率"""
        return fps in cls.VALID_FPS

    @classmethod
    def is_valid_duration(cls, duration: int) -> bool:
        """验证时长"""
        return cls.MIN_DURATION <= duration <= cls.MAX_DURATION

    @classmethod
    def parse_duration(cls, value: str) -> Optional[int]:
        """解析时长"""
        try:
            duration = int(value)
            if cls.is_valid_duration(duration):
                return duration
            return None
        except (ValueError, TypeError):
            return None