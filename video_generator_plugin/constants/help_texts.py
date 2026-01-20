"""帮助文本定义"""

HELP_TEXT = """📹 视频生成插件帮助

【基础命令】
/vg <提示词> - 文生视频（有图时自动图生视频）
/vg r <提示词> - 尾帧图生视频（最近1张图）
/vg fr <提示词> - 首尾帧（最近2张图）

【参数组合】
/vg 720p <提示词> - 指定分辨率
/vg 720p 30 10 <提示词> - 分辨率+帧率+时长

【背景音乐】
/vg mu <提示词> - 添加背景音乐
/vg mu50 <提示词> - 音量50%
/vg cinematic <提示词> - 电影感风格

【预设模板】
/vg <关键词> - 使用预设模板

【查询命令】
/vg c - 当前配置
/vg m - 模型列表
/vg t - 预设模板
/vg s - 任务状态
/vg y - 音乐风格
/vg caps - 当前模型能力
/vg caps <模型ID> - 指定模型能力

【管理命令】
/vg w <模型ID> - 切换模型
/vg d <任务ID> - 取消任务"""


MUSIC_STYLES_TEXT = """🎵 背景音乐风格

【风格列表】
cinematic - 电影感（史诗、大气）
upbeat - 欢快（活泼、积极）
calm - 平静（舒缓、放松）
dramatic - 戏剧性（紧张、冲突）
romantic - 浪漫（温馨、爱情）
sad - 悲伤（忧郁、感伤）
mysterious - 神秘（悬疑、探索）
energetic - 活力（运动、激情）
peaceful - 宁静（自然、冥想）
epic - 史诗（宏大、震撼）

【使用方法】
/vg cinematic <提示词>
/vg mu50 dramatic <提示词>
/vg epic <提示词>

💡 音量格式: mu0-mu100（默认50）"""


CAPS_HELP_TEXT = """🔍 模型能力查询

【使用方法】
/vg caps - 查看当前模型能力
/vg caps <模型ID> - 查看指定模型能力

【能力说明】
📝 文生视频 - 根据文字描述生成视频
🖼️ 图生视频 - 基于图片生成视频
🎬 首帧控制 - 指定视频起始画面
🎞️ 尾帧控制 - 指定视频结束画面
🎵 背景音乐 - 自动生成背景音乐
🎧 自定义音频 - 支持上传音频文件
🎥 多镜头叙事 - 生成多镜头视频

💡 /vg m 查看所有可用模型"""


# 服务商信息
PROVIDER_INFO = {
    "volcengine": {
        "name": "火山引擎",
        "description": "豆包视频生成，支持首尾帧、有声视频",
        "doc_url": "https://www.volcengine.com/docs/82379",
    },
    "aliyun": {
        "name": "阿里云通义万相",
        "description": "万相视频生成，支持图生视频、多镜头",
        "doc_url": "https://help.aliyun.com/document_detail/video-generation.html",
    },
    "zhipu": {
        "name": "智谱 CogVideoX",
        "description": "CogVideoX 视频生成，支持首尾帧",
        "doc_url": "https://open.bigmodel.cn/dev/api",
    },
    "openai": {
        "name": "OpenAI 兼容",
        "description": "兼容 OpenAI 格式的第三方服务",
        "doc_url": "",
    },
}