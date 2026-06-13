"""配置模型定义 - 基于 PluginConfigBase

本模块定义了插件的完整配置模型，用于：
1. 强类型配置访问
2. WebUI 自动生成配置表单
3. 配置验证与默认值生成
"""

from typing import List, Optional
from maibot_sdk import PluginConfigBase, Field


# ==================== 嵌套配置段 ====================

class PluginSection(PluginConfigBase):
    """插件基础设置"""
    __ui_label__ = "插件设置"

    enabled: bool = Field(default=True, description="是否启用插件")
    config_version: str = Field(default="2.2.0", description="配置版本号")


class AdminSection(PluginConfigBase):
    """管理员设置"""
    __ui_label__ = "管理员设置"

    admin_users: List[str] = Field(default_factory=list, description="拥有管理权限的用户 QQ 号列表")


class GenerationSection(PluginConfigBase):
    """生成设置"""
    __ui_label__ = "生成设置"

    default_model: str = Field(default="model1", description="默认使用的模型 ID，可选值: model1, model2, model3, model4")
    default_resolution: str = Field(default="720p", description="默认分辨率，可选值: 480p, 720p, 1080p, 4k")
    default_fps: int = Field(default=24, description="默认帧率，可选值: 15, 24, 30, 60")
    default_duration: int = Field(default=5, description="默认时长（秒），范围 1-60")


class QueueSection(PluginConfigBase):
    """队列设置"""
    __ui_label__ = "队列设置"

    max_queue_size: int = Field(default=10, description="最大任务队列长度")
    task_timeout: int = Field(default=600, description="单个任务的最大等待时间（秒）")
    poll_interval: int = Field(default=5, description="基础轮询间隔（秒）")
    auto_cleanup: bool = Field(default=True, description="自动清理已完成的任务记录")
    cleanup_delay: int = Field(default=3600, description="完成任务保留时间（秒）")


class TemplateItem(PluginConfigBase):
    """单个预设模板"""

    keyword: str = Field(default="", description="触发关键词")
    description: str = Field(default="", description="模板描述")
    prompt: str = Field(default="", description="视频生成提示词")
    resolution: str = Field(default="720p", description="分辨率")
    fps: int = Field(default=24, description="帧率")
    duration: int = Field(default=5, description="时长（秒）")


class TemplatesSection(PluginConfigBase):
    """预设模板设置"""
    __ui_label__ = "预设模板"

    enable_templates: bool = Field(default=True, description="是否启用预设模板功能")
    template_list: List[TemplateItem] = Field(
        default_factory=lambda: [
            TemplateItem(
                keyword="日落",
                description="唯美日落场景",
                prompt="金色的夕阳缓缓落入海平面，天空呈现出橙红色的渐变，海面波光粼粼",
                resolution="1080p",
                fps=24,
                duration=5,
            ),
            TemplateItem(
                keyword="星空",
                description="璀璨星空延时",
                prompt="深邃的夜空中繁星闪烁，银河横跨天际，流星划过",
                resolution="1080p",
                fps=24,
                duration=5,
            ),
        ],
        description="预设模板列表",
    )


class ModelConfig(PluginConfigBase):
    """单个模型配置"""

    name: str = Field(default="", description="模型显示名称")
    format: str = Field(default="", description="服务商类型: volcengine, aliyun, zhipu, openai, kling")
    base_url: str = Field(default="", description="API 基础地址")
    api_key: str = Field(default="", description="API 密钥，支持 ${ENV_VAR} 格式从环境变量读取")
    model: str = Field(default="", description="模型标识符")
    default_resolution: str = Field(default="720p", description="该模型的默认分辨率")
    default_duration: int = Field(default=5, description="该模型的默认时长（秒）")
    prompt_extend: bool = Field(default=True, description="是否启用提示词扩展优化")
    watermark: bool = Field(default=False, description="是否添加服务商水印")
    support_img2video: bool = Field(default=True, description="是否支持图生视频功能")


class ModelsSection(PluginConfigBase):
    """多模型配置"""
    __ui_label__ = "多模型配置"

    hint: str = Field(
        default="支持的服务商：volcengine（火山引擎）、aliyun（阿里云）、zhipu（智谱）、openai（OpenAI兼容）、kling（可灵）",
        description="配置说明",
    )
    model1: ModelConfig = Field(
        default_factory=lambda: ModelConfig(
            name="豆包视频生成",
            format="volcengine",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key="",
            model="doubao-seedance-1-5-pro-251215",
            default_resolution="720p",
            default_duration=5,
            prompt_extend=True,
            watermark=False,
            support_img2video=True,
        ),
        description="模型1 - 火山引擎豆包",
    )
    model2: ModelConfig = Field(
        default_factory=lambda: ModelConfig(
            name="通义万相视频",
            format="aliyun",
            base_url="https://dashscope.aliyuncs.com/api/v1",
            api_key="",
            model="wan2.5-i2v-plus",
            default_resolution="720p",
            default_duration=5,
            prompt_extend=True,
            watermark=False,
            support_img2video=True,
        ),
        description="模型2 - 阿里云通义万相",
    )
    model3: ModelConfig = Field(
        default_factory=lambda: ModelConfig(
            name="智谱CogVideoX",
            format="zhipu",
            base_url="https://open.bigmodel.cn/api",
            api_key="",
            model="cogvideox-3",
            default_resolution="1080p",
            default_duration=5,
            prompt_extend=True,
            watermark=False,
            support_img2video=True,
        ),
        description="模型3 - 智谱CogVideoX",
    )
    model4: ModelConfig = Field(
        default_factory=lambda: ModelConfig(
            name="可灵视频生成",
            format="kling",
            base_url="https://api-beijing.klingai.com",
            api_key="",
            model="kling-v1-6",
            default_resolution="720p",
            default_duration=5,
            prompt_extend=True,
            watermark=False,
            support_img2video=True,
        ),
        description="模型4 - 可灵 Kling",
    )


# ==================== 顶层配置模型 ====================

class VideoGeneratorConfig(PluginConfigBase):
    """视频生成插件完整配置"""
    __ui_label__ = "视频生成插件配置"

    plugin: PluginSection = Field(default_factory=PluginSection)
    admin: AdminSection = Field(default_factory=AdminSection)
    generation: GenerationSection = Field(default_factory=GenerationSection)
    queue: QueueSection = Field(default_factory=QueueSection)
    templates: TemplatesSection = Field(default_factory=TemplatesSection)
    models: ModelsSection = Field(default_factory=ModelsSection)


__all__ = [
    "VideoGeneratorConfig",
    "PluginSection",
    "AdminSection",
    "GenerationSection",
    "QueueSection",
    "TemplatesSection",
    "TemplateItem",
    "ModelsSection",
    "ModelConfig",
]