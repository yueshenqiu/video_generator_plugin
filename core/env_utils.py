"""环境变量工具模块"""

import os
import re
from typing import Any, Dict
from src.common.logger import get_logger

logger = get_logger("video_generator.env")


class EnvUtils:
    """环境变量工具"""
    
    ENV_PATTERN = re.compile(r'\$\{([^}]+)\}')
    
    @classmethod
    def resolve_env_vars(cls, value: Any) -> Any:
        """解析环境变量"""
        if isinstance(value, str):
            return cls._resolve_string(value)
        elif isinstance(value, dict):
            return {k: cls.resolve_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [cls.resolve_env_vars(item) for item in value]
        else:
            return value
    
    @classmethod
    def _resolve_string(cls, value: str) -> str:
        """解析字符串中的环境变量"""
        if not value or '${' not in value:
            return value
        
        def replace_env(match):
            env_name = match.group(1)
            env_value = os.environ.get(env_name, '')
            
            if env_value:
                logger.debug(f"[EnvUtils] 已解析: {env_name}")
            else:
                logger.warning(f"[EnvUtils] 未设置: {env_name}")
            
            return env_value
        
        return cls.ENV_PATTERN.sub(replace_env, value)
    
    @classmethod
    def resolve_api_keys(cls, models_config: Dict[str, Dict]) -> Dict[str, Dict]:
        """解析模型配置中的 API Key"""
        result = {}
        
        for model_id, config in models_config.items():
            if not isinstance(config, dict):
                result[model_id] = config
                continue
            
            new_config = config.copy()
            
            api_key = new_config.get("api_key", "")
            if api_key and '${' in api_key:
                resolved = cls._resolve_string(api_key)
                new_config["api_key"] = resolved
                
                if resolved:
                    logger.info(f"[EnvUtils] 模型 {model_id} API Key 已从环境变量加载")
            
            base_url = new_config.get("base_url", "")
            if base_url and '${' in base_url:
                new_config["base_url"] = cls._resolve_string(base_url)
            
            result[model_id] = new_config
        
        return result