"""配置验证模块 - 适配新版 SDK"""

from typing import List, Any


class ConfigValidator:
    """配置验证器 - 基于强类型配置模型验证"""
    
    SUPPORTED_FORMATS = ["aliyun", "volcengine", "zhipu", "openai", "kling"]
    VALID_RESOLUTIONS = ["720p", "1080p", "480p", "4k"]
    VALID_FPS = [15, 24, 30, 60]
    
    @classmethod
    def validate_all(cls, config, logger=None) -> List[str]:
        """
        验证所有配置
        
        Args:
            config: VideoGeneratorConfig 实例（强类型）
            logger: 日志记录器（ctx.logger）
        
        Returns:
            错误信息列表
        """
        errors = []
        errors.extend(cls._validate_models(config, logger))
        errors.extend(cls._validate_generation(config, logger))
        errors.extend(cls._validate_queue(config, logger))
        return errors
    
    @classmethod
    def _validate_models(cls, config, logger=None) -> List[str]:
        """验证模型配置"""
        errors = []
        
        try:
            models_section = config.models
            model_count = 0
            configured_count = 0
            
            # 动态发现所有 model 属性，不硬编码数量
            model_keys = sorted(
                (k for k in dir(models_section) if k.startswith("model") and k[5:].isdigit()),
                key=lambda x: int(x[5:]),
            )
            for model_key in model_keys:
                model_cfg = getattr(models_section, model_key, None)
                if model_cfg is None:
                    continue
                
                if not model_cfg.format:
                    continue
                
                model_count += 1
                
                if model_cfg.format not in cls.SUPPORTED_FORMATS:
                    errors.append(f"模型 {model_key}: 不支持的 format '{model_cfg.format}'")
                
                if not model_cfg.model:
                    errors.append(f"模型 {model_key}: 缺少 model 标识符")
                
                if model_cfg.api_key:
                    configured_count += 1
            
            if model_count == 0:
                errors.append("没有配置任何模型")
            elif configured_count == 0:
                errors.append("所有模型都没有配置 API Key")
            
            if logger:
                logger.debug(f"模型验证: {model_count} 个模型，{configured_count} 个已配置 API Key")
            
        except Exception as e:
            errors.append(f"验证模型失败: {e}")
        
        return errors
    
    @classmethod
    def _validate_generation(cls, config, logger=None) -> List[str]:
        """验证生成设置"""
        errors = []
        
        try:
            generation = config.generation
            
            if generation.default_fps not in cls.VALID_FPS:
                errors.append(f"默认帧率 {generation.default_fps} 无效，可选值: {cls.VALID_FPS}")
            
            if not isinstance(generation.default_duration, int) or \
               generation.default_duration < 1 or generation.default_duration > 60:
                errors.append(f"默认时长 {generation.default_duration} 无效（范围 1-60）")
            
            if generation.default_resolution not in cls.VALID_RESOLUTIONS:
                errors.append(f"默认分辨率 {generation.default_resolution} 无效")
                
        except Exception as e:
            errors.append(f"验证生成设置失败: {e}")
        
        return errors
    
    @classmethod
    def _validate_queue(cls, config, logger=None) -> List[str]:
        """验证队列设置"""
        errors = []
        
        try:
            queue = config.queue
            
            if not isinstance(queue.max_queue_size, int) or \
               queue.max_queue_size < 1 or queue.max_queue_size > 100:
                errors.append(f"max_queue_size {queue.max_queue_size} 无效（范围 1-100）")
            
            if not isinstance(queue.task_timeout, int) or \
               queue.task_timeout < 60 or queue.task_timeout > 3600:
                errors.append(f"task_timeout {queue.task_timeout} 无效（范围 60-3600）")
            
            if not isinstance(queue.poll_interval, int) or \
               queue.poll_interval < 1 or queue.poll_interval > 60:
                errors.append(f"poll_interval {queue.poll_interval} 无效（范围 1-60）")
                
        except Exception as e:
            errors.append(f"验证队列设置失败: {e}")
        
        return errors
    
    @classmethod
    def validate_and_log(cls, config, logger=None) -> bool:
        """
        验证并记录日志
        
        Args:
            config: VideoGeneratorConfig 实例
            logger: ctx.logger 实例
            
        Returns:
            是否验证通过
        """
        errors = cls.validate_all(config, logger)
        
        if errors:
            if logger:
                logger.warning("配置验证发现问题:")
                for error in errors:
                    logger.warning(f"  - {error}")
            return False
        else:
            if logger:
                logger.debug("配置验证通过")
            return True