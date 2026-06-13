"""常量与配置定义模块"""

from .config_schema import VideoGeneratorConfig
from .music_styles import MUSIC_STYLES, MUSIC_STYLE_DESCRIPTIONS
from .help_texts import HELP_TEXT, MUSIC_STYLES_TEXT, CAPS_HELP_TEXT

__all__ = [
    "VideoGeneratorConfig",
    "MUSIC_STYLES",
    "MUSIC_STYLE_DESCRIPTIONS",
    "HELP_TEXT",
    "MUSIC_STYLES_TEXT",
    "CAPS_HELP_TEXT",
]