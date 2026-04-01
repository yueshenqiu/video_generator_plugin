"""配置定义模块 - WebUI 集成配置

本模块定义了插件的完整配置 Schema，用于：
1. WebUI 自动生成配置表单
2. 配置验证
3. 生成默认配置文件

配置架构说明：
- ConfigField: 单个配置项定义
- ConfigSection: 配置节元数据（标题、图标、描述等）
- ConfigLayout: 页面布局（标签页组织）
- ConfigTab: 单个标签页定义
"""

from src.plugin_system.base.config_types import (
    ConfigField,
    ConfigSection,
    ConfigLayout,
    ConfigTab,
)


CONFIG_SECTIONS = {
    "plugin": ConfigSection(
        title="插件设置",
        description="插件的基本配置项",
        icon="settings",
        collapsed=False,
        order=1
    ),
    "admin": ConfigSection(
        title="管理员设置",
        description="配置拥有管理权限的用户",
        icon="shield",
        collapsed=False,
        order=2
    ),
    "generation": ConfigSection(
        title="生成设置",
        description="视频生成的默认参数配置",
        icon="video",
        collapsed=False,
        order=3
    ),
    "queue": ConfigSection(
        title="队列设置",
        description="任务队列与轮询相关配置",
        icon="list",
        collapsed=False,
        order=4
    ),
    "templates": ConfigSection(
        title="预设模板",
        description="配置视频生成的预设模板，支持关键词快速调用",
        icon="layout",
        collapsed=False,
        order=5
    ),
    "models": ConfigSection(
        title="多模型配置",
        description="配置多个视频生成模型，支持运行时切换",
        icon="cpu",
        collapsed=False,
        order=6
    ),
    "models.model1": ConfigSection(
        title="模型1 - 火山引擎豆包",
        description="火山引擎豆包视频生成模型，支持文生视频、图生视频、首尾帧控制、背景音乐",
        icon="box",
        collapsed=False,
        order=7
    ),
    "models.model2": ConfigSection(
        title="模型2 - 阿里云通义万相",
        description="阿里云通义万相视频生成模型，支持文生视频、图生视频、多镜头叙事",
        icon="box",
        collapsed=True,
        order=8
    ),
    "models.model3": ConfigSection(
        title="模型3 - 智谱CogVideoX",
        description="智谱 CogVideoX 视频生成模型，支持文生视频、图生视频、首尾帧控制",
        icon="box",
        collapsed=True,
        order=9
    ),
    "models.model4": ConfigSection(
        title="模型4 - 可灵 Kling",
        description="可灵视频生成模型，支持文生视频、图生视频（含首尾帧），部分模型支持声音",
        icon="box",
        collapsed=True,
        order=10
    ),
}


CONFIG_SCHEMA = {
    "plugin": {
        "enabled": ConfigField(
            type=bool,
            default=True,
            description="是否启用插件",
            label="启用插件",
            hint="关闭后插件将不响应任何命令",
            order=1
        ),
        "config_version": ConfigField(
            type=str,
            default="2.2.0",
            description="配置版本号",
            label="配置版本",
            disabled=True,
            hidden=True,
            order=99
        ),
    },

    "admin": {
        "admin_users": ConfigField(
            type=list,
            default=[],
            description="拥有管理权限的用户 QQ 号列表",
            label="管理员列表",
            item_type="string",
            placeholder="输入 QQ 号",
            hint="管理员可以切换模型、取消任务等",
            max_items=20,
            order=1
        ),
    },

    "generation": {
        "default_model": ConfigField(
            type=str,
            default="model1",
            description="默认使用的模型 ID",
            label="默认模型",
            choices=["model1", "model2", "model3", "model4"],
            hint="可通过 /vg w 命令切换",
            order=1
        ),
        "default_resolution": ConfigField(
            type=str,
            default="720p",
            description="默认分辨率",
            label="默认分辨率",
            choices=["480p", "720p", "1080p", "4k"],
            hint="部分模型可能不支持所有分辨率",
            order=2
        ),
        "default_fps": ConfigField(
            type=int,
            default=24,
            description="默认帧率",
            label="默认帧率",
            choices=[15, 24, 30, 60],
            hint="帧率越高视频越流畅，但生成时间更长",
            order=3
        ),
        "default_duration": ConfigField(
            type=int,
            default=5,
            description="默认时长（秒）",
            label="默认时长",
            min=1,
            max=30,
            step=1,
            hint="不同模型支持的时长范围不同",
            order=4
        ),
    },

    "queue": {
        "max_queue_size": ConfigField(
            type=int,
            default=10,
            description="最大任务队列长度",
            label="队列大小",
            min=1,
            max=100,
            step=1,
            hint="超出队列限制的任务将被拒绝",
            order=1
        ),
        "task_timeout": ConfigField(
            type=int,
            default=600,
            description="单个任务的最大等待时间（秒）",
            label="任务超时",
            min=60,
            max=1800,
            step=30,
            hint="超时后任务将被标记为失败",
            order=2
        ),
        "poll_interval": ConfigField(
            type=int,
            default=5,
            description="基础轮询间隔（秒）",
            label="轮询间隔",
            min=1,
            max=30,
            step=1,
            hint="插件使用智能轮询，此为初始间隔",
            order=3
        ),
        "auto_cleanup": ConfigField(
            type=bool,
            default=True,
            description="自动清理已完成的任务记录",
            label="自动清理",
            hint="开启后完成的任务会在指定时间后清理",
            order=4
        ),
        "cleanup_delay": ConfigField(
            type=int,
            default=3600,
            description="完成任务保留时间（秒）",
            label="清理延迟",
            min=60,
            max=86400,
            step=60,
            depends_on="queue.auto_cleanup",
            depends_value=True,
            hint="任务完成后多久清理记录",
            order=5
        ),
    },

    "templates": {
        "enable_templates": ConfigField(
            type=bool,
            default=True,
            description="是否启用预设模板功能",
            label="启用模板",
            hint="启用后可通过关键词快速调用预设参数",
            order=1
        ),
        "template_list": ConfigField(
            type=list,
            default=[
                {
                    "keyword": "日落",
                    "description": "唯美日落场景",
                    "prompt": "金色的夕阳缓缓落入海平面，天空呈现出橙红色的渐变，海面波光粼粼",
                    "resolution": "1080p",
                    "fps": 24,
                    "duration": 5
                },
                {
                    "keyword": "星空",
                    "description": "璀璨星空延时",
                    "prompt": "深邃的夜空中繁星闪烁，银河横跨天际，流星划过",
                    "resolution": "1080p",
                    "fps": 24,
                    "duration": 5
                },
            ],
            description="预设模板列表",
            label="模板列表",
            item_type="object",
            item_fields={
                "keyword": {"type": "string", "label": "关键词", "placeholder": "触发关键词", "required": True},
                "description": {"type": "string", "label": "描述", "placeholder": "模板描述（可选）"},
                "prompt": {"type": "string", "label": "提示词", "placeholder": "视频生成提示词", "required": True},
                "resolution": {"type": "string", "label": "分辨率", "default": "720p", "choices": ["480p", "720p", "1080p"]},
                "fps": {"type": "number", "label": "帧率", "default": 24},
                "duration": {"type": "number", "label": "时长", "default": 5},
            },
            min_items=0,
            max_items=50,
            depends_on="templates.enable_templates",
            depends_value=True,
            hint="使用 /vg <关键词> 快速生成",
            order=2
        ),
    },

    "models": {
        "hint": ConfigField(
            type=str,
            default="以下配置多个视频生成模型，支持的服务商：volcengine（火山引擎）、aliyun（阿里云）、zhipu（智谱）、openai（OpenAI兼容）、kling（可灵）",
            description="配置说明",
            label="说明",
            disabled=True,
            order=1
        ),
    },

    "models.model1": {
        "name": ConfigField(type=str, default="豆包视频生成", description="模型显示名称", label="模型名称", order=1),
        "format": ConfigField(
            type=str, default="volcengine", description="API 格式/服务商类型", label="服务商",
            choices=["volcengine", "aliyun", "zhipu", "openai", "kling"], order=2
        ),
        "base_url": ConfigField(type=str, default="https://ark.cn-beijing.volces.com/api/v3", description="API 基础地址", label="API 地址", order=3),
        "api_key": ConfigField(type=str, default="", description="API 密钥，支持 ${ENV_VAR} 格式从环境变量读取", label="API Key", input_type="password", required=True, order=4),
        "model": ConfigField(type=str, default="doubao-seedance-1-5-pro-251215", description="模型标识符", label="模型ID", order=5),
        "default_resolution": ConfigField(type=str, default="720p", description="该模型的默认分辨率", label="默认分辨率", choices=["720p", "1080p"], order=6),
        "default_duration": ConfigField(type=int, default=5, description="该模型的默认时长（秒）", label="默认时长", min=5, max=10, order=7),
        "prompt_extend": ConfigField(type=bool, default=True, description="是否启用提示词扩展优化", label="提示词扩展", order=8),
        "watermark": ConfigField(type=bool, default=False, description="是否添加服务商水印", label="添加水印", order=9),
        "support_img2video": ConfigField(type=bool, default=True, description="是否支持图生视频功能", label="图生视频", order=10),
    },

    "models.model2": {
        "name": ConfigField(type=str, default="通义万相视频", description="模型显示名称", label="模型名称", order=1),
        "format": ConfigField(
            type=str, default="aliyun", description="API 格式/服务商类型", label="服务商",
            choices=["volcengine", "aliyun", "zhipu", "openai", "kling"], order=2
        ),
        "base_url": ConfigField(type=str, default="https://dashscope.aliyuncs.com/api/v1", description="API 基础地址", label="API 地址", order=3),
        "api_key": ConfigField(type=str, default="", description="API 密钥", label="API Key", input_type="password", order=4),
        "model": ConfigField(type=str, default="wan2.5-i2v-plus", description="模型标识符", label="模型ID", order=5),
        "default_resolution": ConfigField(type=str, default="720p", description="该模型的默认分辨率", label="默认分辨率", choices=["480p", "720p", "1080p"], order=6),
        "default_duration": ConfigField(type=int, default=5, description="该模型的默认时长（秒）", label="默认时长", min=2, max=15, order=7),
        "prompt_extend": ConfigField(type=bool, default=True, description="是否启用提示词扩展", label="提示词扩展", order=8),
        "watermark": ConfigField(type=bool, default=False, description="是否添加水印", label="添加水印", order=9),
        "support_img2video": ConfigField(type=bool, default=True, description="是否支持图生视频", label="图生视频", order=10),
    },

    "models.model3": {
        "name": ConfigField(type=str, default="智谱CogVideoX", description="模型显示名称", label="模型名称", order=1),
        "format": ConfigField(
            type=str, default="zhipu", description="API 格式/服务商类型", label="服务商",
            choices=["volcengine", "aliyun", "zhipu", "openai", "kling"], order=2
        ),
        "base_url": ConfigField(type=str, default="https://open.bigmodel.cn/api", description="API 基础地址", label="API 地址", order=3),
        "api_key": ConfigField(type=str, default="", description="API 密钥", label="API Key", input_type="password", order=4),
        "model": ConfigField(type=str, default="cogvideox-3", description="模型标识符", label="模型ID", order=5),
        "default_resolution": ConfigField(type=str, default="1080p", description="该模型的默认分辨率", label="默认分辨率", choices=["720p", "1080p", "4k"], order=6),
        "default_duration": ConfigField(type=int, default=5, description="该模型的默认时长（秒）", label="默认时长", min=5, max=10, order=7),
        "prompt_extend": ConfigField(type=bool, default=True, description="是否启用提示词扩展", label="提示词扩展", order=8),
        "watermark": ConfigField(type=bool, default=False, description="是否添加水印", label="添加水印", order=9),
        "support_img2video": ConfigField(type=bool, default=True, description="是否支持图生视频", label="图生视频", order=10),
    },

    "models.model4": {
        "name": ConfigField(
            type=str,
            default="可灵视频生成",
            description="模型显示名称",
            label="模型名称",
            order=1
        ),
        "format": ConfigField(
            type=str,
            default="kling",
            description="API 格式/服务商类型",
            label="服务商",
            choices=["volcengine", "aliyun", "zhipu", "openai", "kling"],
            order=2
        ),
        "base_url": ConfigField(
            type=str,
            default="https://api-beijing.klingai.com",
            description="API 基础地址",
            label="API 地址",
            hint="默认北京站点",
            order=3
        ),
        "api_key": ConfigField(
            type=str,
            default="",
            description="API 密钥",
            label="API Key",
            input_type="password",
            placeholder="输入 API Key 或 ${环境变量名}",
            required=False,
            order=4
        ),
        "model": ConfigField(
            type=str,
            default="kling-v1-6",
            description="模型标识符",
            label="模型ID",
            hint="如 kling-v1-6 / kling-v2-5-turbo / kling-v2-6",
            order=5
        ),
        "default_resolution": ConfigField(
            type=str,
            default="720p",
            description="默认分辨率（将映射为宽高比）",
            label="默认分辨率",
            choices=["480p", "720p", "1080p", "4k"],
            order=6
        ),
        "default_duration": ConfigField(
            type=int,
            default=5,
            description="默认时长（秒）",
            label="默认时长",
            min=3,
            max=10,
            order=7
        ),
        "prompt_extend": ConfigField(
            type=bool,
            default=True,
            description="提示词扩展（当前仅保留配置）",
            label="提示词扩展",
            order=8
        ),
        "watermark": ConfigField(
            type=bool,
            default=False,
            description="是否生成水印版本",
            label="添加水印",
            order=9
        ),
        "support_img2video": ConfigField(
            type=bool,
            default=True,
            description="是否支持图生视频",
            label="图生视频",
            order=10
        ),
    },
}


CONFIG_LAYOUT = ConfigLayout(
    type="tabs",
    tabs=[
        ConfigTab(
            id="basic",
            title="基础设置",
            sections=["plugin", "admin", "generation"],
            icon="settings",
            order=1
        ),
        ConfigTab(
            id="models",
            title="模型管理",
            sections=["models", "models.model1", "models.model2", "models.model3", "models.model4"],
            icon="cpu",
            order=2
        ),
        ConfigTab(
            id="templates",
            title="预设模板",
            sections=["templates"],
            icon="layout",
            order=3
        ),
        ConfigTab(
            id="advanced",
            title="高级设置",
            sections=["queue"],
            icon="sliders",
            order=4
        ),
    ]
)


__all__ = [
    "CONFIG_SCHEMA",
    "CONFIG_SECTIONS",
    "CONFIG_LAYOUT",
]