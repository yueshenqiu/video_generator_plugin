"""环境变量工具模块"""

import os
import re
import logging
from typing import Any, Dict, Optional


class EnvUtils:
    """环境变量工具"""
    
    ENV_PATTERN = re.compile(r'\$\{([^}]+)\}')
    
    @classmethod
    def resolve_env_vars(cls, value: Any, logger: Optional[logging.Logger] = None) -> Any:
        if isinstance(value, str):
            return cls._resolve_string(value, logger)
        elif isinstance(value, dict):
            return {k: cls.resolve_env_vars(v, logger) for k, v in value.items()}
        elif isinstance(value, list):
            return [cls.resolve_env_vars(item, logger) for item in value]
        else:
            return value
    
    @classmethod
    def _resolve_string(cls, value: str, logger: Optional[logging.Logger] = None) -> str:
        if not value or '${' not in value:
            return value
        
        _logger = logger or logging.getLogger("video_generator.env")
        
        def replace_env(match):
            env_name = match.group(1)
            env_value = os.environ.get(env_name, '')
            
            if env_value:
                _logger.debug(f"[EnvUtils] 已解析: {env_name}")
            else:
                _logger.debug(f"[EnvUtils] 未设置: {env_name}")
            
            return env_value
        
        return cls.ENV_PATTERN.sub(replace_env, value)
    
    @classmethod
    def resolve_api_keys(
        cls,
        models_config: Dict[str, Dict],
        logger: Optional[logging.Logger] = None,
    ) -> Dict[str, Dict]:
        _logger = logger or logging.getLogger("video_generator.env")
        result = {}
        
        for model_id, config in models_config.items():
            if not isinstance(config, dict):
                result[model_id] = config
                continue
            
            new_config = config.copy()
            
            api_key = new_config.get("api_key", "")
            if api_key and '${' in api_key:
                resolved = cls._resolve_string(api_key, _logger)
                new_config["api_key"] = resolved
                if resolved:
                    _logger.info(f"[EnvUtils] 模型 {model_id} API Key 已从环境变量加载")
            
            base_url = new_config.get("base_url", "")
            if base_url and '${' in base_url:
                new_config["base_url"] = cls._resolve_string(base_url, _logger)
            
            result[model_id] = new_config
        
        return result