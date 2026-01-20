"""服务商模块初始化"""

from .base import BaseProvider
from .capabilities import (
    ProviderCapabilities,
    ModelCapabilities,
    VideoFeature,
    AudioFeature,
    ResolutionSupport,
    DurationSupport,
    FpsSupport,
    get_provider_capabilities,
    get_model_capabilities,
    PROVIDER_CAPABILITIES,
)

# 延迟导入具体服务商，避免循环导入
_provider_classes = {}


def _load_providers():
    """加载所有服务商类"""
    global _provider_classes
    if _provider_classes:
        return _provider_classes
    
    from .aliyun import AliyunProvider
    from .volcengine import VolcengineProvider
    from .zhipu import ZhipuProvider
    from .openai_compatible import OpenAICompatibleProvider
    
    _provider_classes = {
        "aliyun": AliyunProvider,
        "volcengine": VolcengineProvider,
        "zhipu": ZhipuProvider,
        "openai": OpenAICompatibleProvider,
    }
    return _provider_classes


def get_provider_class(format_name: str):
    """根据格式名获取服务商类"""
    providers = _load_providers()
    return providers.get(format_name)


def get_supported_formats():
    """获取支持的服务商格式列表"""
    providers = _load_providers()
    return list(providers.keys())


__all__ = [
    # 基类
    "BaseProvider",
    # 能力声明
    "ProviderCapabilities",
    "ModelCapabilities",
    "VideoFeature",
    "AudioFeature",
    "ResolutionSupport",
    "DurationSupport",
    "FpsSupport",
    "get_provider_capabilities",
    "get_model_capabilities",
    "PROVIDER_CAPABILITIES",
    # 服务商获取
    "get_provider_class",
    "get_supported_formats",
]