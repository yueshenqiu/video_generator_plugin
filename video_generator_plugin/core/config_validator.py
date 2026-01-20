"""配置验证模块"""

from typing import List
from src.common.logger import get_logger

logger = get_logger("video_generator.config")


class ConfigValidator:
    """配置验证器"""
    
    SUPPORTED_FORMATS = ["aliyun", "volcengine"]
    VALID_RESOLUTIONS = ["720p", "1080p", "480p", "4k"]
    VALID_FPS = [15, 24, 30]
    
    @classmethod
    def validate_all(cls, plugin) -> List[str]:
        """验证所有配置"""
        errors = []
        errors.extend(cls._validate_models(plugin))
        errors.extend(cls._validate_generation(plugin))
        errors.extend(cls._validate_queue(plugin))
        return errors
    
    @classmethod
    def _validate_models(cls, plugin) -> List[str]:
        """验证模型配置"""
        errors = []
        
        try:
            models = plugin.get_config("models", {})
            if not isinstance(models, dict):
                errors.append("models 配置格式错误")
                return errors
            
            model_count = 0
            configured_count = 0
            
            for model_id, config in models.items():
                if not isinstance(config, dict) or "format" not in config:
                    continue
                
                model_count += 1
                
                if not config.get("format"):
                    errors.append(f"模型 {model_id}: 缺少 format")
                elif config.get("format") not in cls.SUPPORTED_FORMATS:
                    errors.append(f"模型 {model_id}: 不支持的 format")
                
                if not config.get("model"):
                    errors.append(f"模型 {model_id}: 缺少 model")
                
                if config.get("api_key"):
                    configured_count += 1
            
            if model_count == 0:
                errors.append("没有配置任何模型")
            elif configured_count == 0:
                errors.append("所有模型都没有配置 API Key")
            
            logger.info(f"[ConfigValidator] 模型: {model_count} 个，{configured_count} 个已配置")
            
        except Exception as e:
            errors.append(f"验证模型失败: {e}")
        
        return errors
    
    @classmethod
    def _validate_generation(cls, plugin) -> List[str]:
        """验证生成设置"""
        errors = []
        
        try:
            default_fps = plugin.get_config("generation.default_fps", 24)
            if default_fps not in cls.VALID_FPS:
                errors.append(f"默认帧率 {default_fps} 无效")
            
            default_duration = plugin.get_config("generation.default_duration", 5)
            if not isinstance(default_duration, int) or default_duration < 1 or default_duration > 60:
                errors.append(f"默认时长 {default_duration} 无效")
                
        except Exception as e:
            errors.append(f"验证生成设置失败: {e}")
        
        return errors
    
    @classmethod
    def _validate_queue(cls, plugin) -> List[str]:
        """验证队列设置"""
        errors = []
        
        try:
            max_queue = plugin.get_config("queue.max_queue_size", 10)
            if not isinstance(max_queue, int) or max_queue < 1 or max_queue > 100:
                errors.append(f"max_queue_size {max_queue} 无效")
            
            timeout = plugin.get_config("queue.task_timeout", 600)
            if not isinstance(timeout, int) or timeout < 60 or timeout > 3600:
                errors.append(f"task_timeout {timeout} 无效")
                
        except Exception as e:
            errors.append(f"验证队列设置失败: {e}")
        
        return errors
    
    @classmethod
    def validate_and_log(cls, plugin) -> bool:
        """验证并记录日志"""
        errors = cls.validate_all(plugin)
        
        if errors:
            logger.warning("[ConfigValidator] 配置问题:")
            for error in errors:
                logger.warning(f"  - {error}")
            return False
        else:
            logger.info("[ConfigValidator] 配置验证通过")
            return True