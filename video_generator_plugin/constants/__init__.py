"""常量模块初始化"""

from .music_styles import MUSIC_STYLES, MUSIC_STYLE_DESCRIPTIONS
from .help_texts import HELP_TEXT, MUSIC_STYLES_TEXT
from .config_schema import CONFIG_SCHEMA, CONFIG_SECTIONS, CONFIG_LAYOUT

__all__ = [
    "MUSIC_STYLES",
    "MUSIC_STYLE_DESCRIPTIONS",
    "HELP_TEXT",
    "MUSIC_STYLES_TEXT",
    "CONFIG_SCHEMA",
    "CONFIG_SECTIONS",
    "CONFIG_LAYOUT",
]