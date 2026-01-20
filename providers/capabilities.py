"""服务商能力声明系统"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum, auto


class VideoFeature(Enum):
    """视频生成特性"""
    TEXT_TO_VIDEO = auto()      # 文生视频
    IMAGE_TO_VIDEO = auto()     # 图生视频
    FIRST_FRAME = auto()        # 首帧控制
    LAST_FRAME = auto()         # 尾帧控制
    VIDEO_EXTEND = auto()       # 视频续写
    STYLE_TRANSFER = auto()     # 风格迁移
    MOTION_BRUSH = auto()       # 运动笔刷
    CAMERA_CONTROL = auto()     # 镜头控制
    MULTI_SHOT = auto()         # 多镜头叙事


class AudioFeature(Enum):
    """音频特性"""
    BACKGROUND_MUSIC = auto()   # 背景音乐生成
    AUDIO_INPUT = auto()        # 自定义音频输入
    LIP_SYNC = auto()           # 口型同步
    VOICE_CLONE = auto()        # 声音克隆
    AUTO_SOUND = auto()         # 自动音效


@dataclass
class ResolutionSupport:
    """分辨率支持"""
    presets: List[str] = field(default_factory=lambda: ["720p", "1080p"])
    custom: bool = False
    min_size: int = 480
    max_size: int = 1920
    aspect_ratios: List[str] = field(default_factory=lambda: ["16:9", "9:16", "1:1"])
    
    def supports_resolution(self, resolution: str) -> bool:
        """检查是否支持指定分辨率"""
        return resolution.lower() in [r.lower() for r in self.presets]


@dataclass
class DurationSupport:
    """时长支持"""
    min_seconds: int = 1
    max_seconds: int = 10
    step_seconds: int = 1
    allowed_values: Optional[List[int]] = None  # 如果有固定可选值
    
    def validate_duration(self, duration: int) -> int:
        """验证并调整时长"""
        if self.allowed_values:
            # 找最接近的允许值
            closest = min(self.allowed_values, key=lambda x: abs(x - duration))
            return closest
        return max(self.min_seconds, min(duration, self.max_seconds))


@dataclass
class FpsSupport:
    """帧率支持"""
    allowed_values: List[int] = field(default_factory=lambda: [24, 30])
    default: int = 24
    
    def validate_fps(self, fps: int) -> int:
        """验证并调整帧率"""
        if fps in self.allowed_values:
            return fps
        # 找最接近的允许值
        return min(self.allowed_values, key=lambda x: abs(x - fps))


@dataclass
class ModelCapabilities:
    """单个模型的能力声明"""
    model_id: str
    display_name: str
    
    # 视频特性
    video_features: List[VideoFeature] = field(default_factory=list)
    
    # 音频特性
    audio_features: List[AudioFeature] = field(default_factory=list)
    
    # 分辨率支持
    resolution: ResolutionSupport = field(default_factory=ResolutionSupport)
    
    # 时长支持
    duration: DurationSupport = field(default_factory=DurationSupport)
    
    # 帧率支持
    fps: FpsSupport = field(default_factory=FpsSupport)
    
    # 其他限制
    max_prompt_length: int = 2000
    supports_negative_prompt: bool = False
    
    def supports(self, feature: VideoFeature) -> bool:
        """检查是否支持某视频特性"""
        return feature in self.video_features
    
    def supports_audio(self, feature: AudioFeature) -> bool:
        """检查是否支持某音频特性"""
        return feature in self.audio_features
    
    def has_img2video(self) -> bool:
        """是否支持图生视频"""
        return VideoFeature.IMAGE_TO_VIDEO in self.video_features
    
    def has_first_frame(self) -> bool:
        """是否支持首帧"""
        return VideoFeature.FIRST_FRAME in self.video_features
    
    def has_last_frame(self) -> bool:
        """是否支持尾帧"""
        return VideoFeature.LAST_FRAME in self.video_features
    
    def has_audio(self) -> bool:
        """是否支持音频生成"""
        return len(self.audio_features) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于显示）"""
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "video_features": [f.name for f in self.video_features],
            "audio_features": [f.name for f in self.audio_features],
            "resolutions": self.resolution.presets,
            "duration_range": f"{self.duration.min_seconds}-{self.duration.max_seconds}秒",
            "fps": self.fps.allowed_values,
        }


@dataclass
class ProviderCapabilities:
    """服务商能力声明"""
    provider_name: str
    display_name: str
    
    # 支持的模型
    models: Dict[str, ModelCapabilities] = field(default_factory=dict)
    
    # API 特性
    supports_async: bool = True         # 支持异步任务
    supports_cancel: bool = False       # 支持取消任务
    supports_webhook: bool = False      # 支持 Webhook 回调
    
    # 限制
    rate_limit_rpm: int = 60           # 每分钟请求限制
    concurrent_tasks: int = 5          # 并发任务数
    
    def get_model(self, model_id: str) -> Optional[ModelCapabilities]:
        """获取模型能力"""
        return self.models.get(model_id)
    
    def get_model_list(self) -> List[str]:
        """获取模型列表"""
        return list(self.models.keys())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于显示）"""
        return {
            "provider_name": self.provider_name,
            "display_name": self.display_name,
            "supports_cancel": self.supports_cancel,
            "models": {k: v.to_dict() for k, v in self.models.items()},
        }


# ==================== 预定义的能力声明 ====================

# 火山引擎能力声明
VOLCENGINE_CAPABILITIES = ProviderCapabilities(
    provider_name="volcengine",
    display_name="火山引擎",
    supports_cancel=True,
    models={
        "doubao-seedance-1-5-pro-251215": ModelCapabilities(
            model_id="doubao-seedance-1-5-pro-251215",
            display_name="豆包 Seedance 1.5 Pro",
            video_features=[
                VideoFeature.TEXT_TO_VIDEO,
                VideoFeature.IMAGE_TO_VIDEO,
                VideoFeature.FIRST_FRAME,
                VideoFeature.LAST_FRAME,
            ],
            audio_features=[
                AudioFeature.BACKGROUND_MUSIC,
                AudioFeature.AUTO_SOUND,
            ],
            resolution=ResolutionSupport(
                presets=["720p", "1080p"],
                aspect_ratios=["16:9", "9:16", "1:1"],
            ),
            duration=DurationSupport(
                min_seconds=5,
                max_seconds=10,
                allowed_values=[5, 10],
            ),
            fps=FpsSupport(allowed_values=[24], default=24),
        ),
        "doubao-seedance-1-0-pro-250528": ModelCapabilities(
            model_id="doubao-seedance-1-0-pro-250528",
            display_name="豆包 Seedance 1.0 Pro",
            video_features=[
                VideoFeature.TEXT_TO_VIDEO,
                VideoFeature.IMAGE_TO_VIDEO,
                VideoFeature.FIRST_FRAME,
                VideoFeature.LAST_FRAME,
            ],
            audio_features=[],  # 1.0 不支持音频
            resolution=ResolutionSupport(
                presets=["720p", "1080p"],
            ),
            duration=DurationSupport(
                min_seconds=5,
                max_seconds=5,
                allowed_values=[5],
            ),
            fps=FpsSupport(allowed_values=[24], default=24),
        ),
    }
)

# 阿里云能力声明
ALIYUN_CAPABILITIES = ProviderCapabilities(
    provider_name="aliyun",
    display_name="阿里云通义万相",
    supports_cancel=False,
    models={
        "wan2.6-i2v-flash": ModelCapabilities(
            model_id="wan2.6-i2v-flash",
            display_name="万相 2.6 Flash",
            video_features=[
                VideoFeature.IMAGE_TO_VIDEO,
                VideoFeature.FIRST_FRAME,
                VideoFeature.MULTI_SHOT,
            ],
            audio_features=[
                AudioFeature.BACKGROUND_MUSIC,
                AudioFeature.AUDIO_INPUT,
                AudioFeature.AUTO_SOUND,
            ],
            resolution=ResolutionSupport(presets=["720p", "1080p"]),
            duration=DurationSupport(min_seconds=2, max_seconds=15),
            fps=FpsSupport(allowed_values=[30], default=30),
        ),
        "wan2.5-i2v-plus": ModelCapabilities(
            model_id="wan2.5-i2v-plus",
            display_name="万相 2.5 Plus (图生视频)",
            video_features=[
                VideoFeature.IMAGE_TO_VIDEO,
                VideoFeature.FIRST_FRAME,
            ],
            audio_features=[
                AudioFeature.BACKGROUND_MUSIC,
                AudioFeature.AUDIO_INPUT,
            ],
            resolution=ResolutionSupport(presets=["480p", "720p", "1080p"]),
            duration=DurationSupport(min_seconds=5, max_seconds=10, allowed_values=[5, 10]),
            fps=FpsSupport(allowed_values=[30], default=30),
        ),
        "wan2.5-t2v-turbo": ModelCapabilities(
            model_id="wan2.5-t2v-turbo",
            display_name="万相 2.5 Turbo (文生视频)",
            video_features=[
                VideoFeature.TEXT_TO_VIDEO,
            ],
            audio_features=[],
            resolution=ResolutionSupport(presets=["480p", "720p", "1080p"]),
            duration=DurationSupport(min_seconds=5, max_seconds=5, allowed_values=[5]),
            fps=FpsSupport(allowed_values=[30], default=30),
        ),
    }
)

# 智谱能力声明
ZHIPU_CAPABILITIES = ProviderCapabilities(
    provider_name="zhipu",
    display_name="智谱 CogVideoX",
    supports_cancel=False,
    models={
        "cogvideox-3": ModelCapabilities(
            model_id="cogvideox-3",
            display_name="CogVideoX-3",
            video_features=[
                VideoFeature.TEXT_TO_VIDEO,
                VideoFeature.IMAGE_TO_VIDEO,
                VideoFeature.FIRST_FRAME,
                VideoFeature.LAST_FRAME,
            ],
            audio_features=[
                AudioFeature.AUTO_SOUND,
            ],
            resolution=ResolutionSupport(
                presets=["720p", "1080p", "4k"],
                aspect_ratios=["16:9", "9:16", "1:1"],
            ),
            duration=DurationSupport(min_seconds=5, max_seconds=10, allowed_values=[5, 10]),
            fps=FpsSupport(allowed_values=[30, 60], default=30),
        ),
        "cogvideox-2": ModelCapabilities(
            model_id="cogvideox-2",
            display_name="CogVideoX-2",
            video_features=[
                VideoFeature.TEXT_TO_VIDEO,
                VideoFeature.IMAGE_TO_VIDEO,
            ],
            audio_features=[],
            resolution=ResolutionSupport(presets=["720p", "1080p"]),
            duration=DurationSupport(min_seconds=5, max_seconds=5, allowed_values=[5]),
            fps=FpsSupport(allowed_values=[30, 60], default=30),
        ),
    }
)

# OpenAI 兼容（通用）
OPENAI_CAPABILITIES = ProviderCapabilities(
    provider_name="openai",
    display_name="OpenAI 兼容",
    supports_cancel=False,
    models={}  # 动态模型，不预定义
)


# 能力声明映射
PROVIDER_CAPABILITIES: Dict[str, ProviderCapabilities] = {
    "volcengine": VOLCENGINE_CAPABILITIES,
    "aliyun": ALIYUN_CAPABILITIES,
    "zhipu": ZHIPU_CAPABILITIES,
    "openai": OPENAI_CAPABILITIES,
}


def get_provider_capabilities(provider_name: str) -> Optional[ProviderCapabilities]:
    """获取服务商能力声明"""
    return PROVIDER_CAPABILITIES.get(provider_name)


def get_model_capabilities(provider_name: str, model_id: str) -> Optional[ModelCapabilities]:
    """获取模型能力声明"""
    provider_caps = get_provider_capabilities(provider_name)
    if provider_caps:
        return provider_caps.get_model(model_id)
    return None