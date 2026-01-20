"""视频生成器模块"""

from typing import Dict, Any, Optional, List, Tuple

from src.common.logger import get_logger
from .env_utils import EnvUtils
from ..providers import get_provider_class, get_provider_capabilities

logger = get_logger("video_generator.generator")


class VideoGenerator:
    """视频生成器 - 统一管理多模型视频生成"""

    def __init__(self, models_config: Dict[str, Dict[str, Any]], default_model: str = "model1"):
        """
        初始化视频生成器
        
        Args:
            models_config: 模型配置字典
            default_model: 默认模型ID
        """
        # 解析环境变量
        self._models_config = EnvUtils.resolve_api_keys(models_config)
        self._current_model_id = default_model
        self._provider_instances: Dict[str, Any] = {}
        
        # 统计可用模型
        available_count = sum(1 for cfg in self._models_config.values() 
                            if isinstance(cfg, dict) and cfg.get("api_key"))
        total_count = sum(1 for cfg in self._models_config.values() 
                        if isinstance(cfg, dict) and cfg.get("format"))
        
        logger.info(f"[VideoGenerator] 初始化: {total_count} 个模型，{available_count} 个已配置")
        logger.info(f"[VideoGenerator] 默认模型: {default_model}")

    def _get_provider_instance(self, model_id: str):
        """获取模型对应的服务商实例"""
        if model_id not in self._models_config:
            logger.error(f"[VideoGenerator] 模型 {model_id} 不存在")
            return None
            
        model_config = self._models_config[model_id]
        
        if not isinstance(model_config, dict):
            logger.error(f"[VideoGenerator] 模型 {model_id} 配置格式错误")
            return None
        
        api_key = model_config.get("api_key", "")
        
        if not api_key:
            logger.error(f"[VideoGenerator] 模型 {model_id} 未配置 API Key")
            return None
        
        if model_id not in self._provider_instances:
            api_format = model_config.get("format", "aliyun")
            base_url = model_config.get("base_url", "")
            
            # 获取服务商类
            provider_class = get_provider_class(api_format)
            
            if not provider_class:
                logger.error(f"[VideoGenerator] 不支持的 API 格式: {api_format}")
                return None
            
            try:
                self._provider_instances[model_id] = provider_class(
                    api_key=api_key,
                    base_url=base_url
                )
                logger.info(f"[VideoGenerator] 初始化服务商: {model_id} ({api_format})")
            except Exception as e:
                logger.error(f"[VideoGenerator] 初始化服务商失败: {e}")
                return None
                
        return self._provider_instances[model_id]

    def get_available_models(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有可用模型的信息（按服务商分组）"""
        result = {}
        
        for model_id, config in self._models_config.items():
            if not isinstance(config, dict) or not config.get("format"):
                continue
                
            api_format = config.get("format", "unknown")
            if api_format not in result:
                result[api_format] = []
            
            result[api_format].append({
                "id": model_id,
                "name": config.get("name", model_id),
                "model": config.get("model", ""),
                "has_api_key": bool(config.get("api_key")),
                "support_img2video": config.get("support_img2video", True),
            })
        
        return result

    def get_model_list(self) -> List[Dict[str, Any]]:
        """获取模型列表"""
        result = []
        for model_id, config in self._models_config.items():
            if not isinstance(config, dict) or not config.get("format"):
                continue
                
            result.append({
                "id": model_id,
                "name": config.get("name", model_id),
                "model": config.get("model", ""),
                "format": config.get("format", "unknown"),
                "has_api_key": bool(config.get("api_key")),
                "support_img2video": config.get("support_img2video", True),
                "is_current": model_id == self._current_model_id,
            })
        return result

    def get_current_model_id(self) -> str:
        """获取当前模型ID"""
        return self._current_model_id

    def get_current_model_config(self) -> Dict[str, Any]:
        """获取当前模型配置"""
        return self._models_config.get(self._current_model_id, {})

    def get_model_config(self, model_id: str) -> Optional[Dict[str, Any]]:
        """获取指定模型的配置"""
        config = self._models_config.get(model_id)
        if isinstance(config, dict) and config.get("format"):
            return config
        return None

    def get_model_capabilities(self, model_id: str) -> Optional[Dict[str, Any]]:
        """获取模型能力信息"""
        config = self.get_model_config(model_id)
        if not config:
            return None
        
        api_format = config.get("format", "")
        model_name = config.get("model", "")
        
        # 获取服务商能力声明
        provider_caps = get_provider_capabilities(api_format)
        if provider_caps:
            model_caps = provider_caps.get_model(model_name)
            if model_caps:
                return model_caps.to_dict()
        
        # 返回配置中的基本信息
        return {
            "model_id": model_id,
            "display_name": config.get("name", model_id),
            "format": api_format,
            "support_img2video": config.get("support_img2video", True),
        }

    def switch_model(self, model_id: str) -> bool:
        """切换当前模型"""
        if model_id not in self._models_config:
            logger.warning(f"[VideoGenerator] 切换失败: 模型 {model_id} 不存在")
            return False
        
        config = self._models_config[model_id]
        if not isinstance(config, dict) or not config.get("format"):
            logger.warning(f"[VideoGenerator] 切换失败: 模型 {model_id} 配置无效")
            return False
        
        if not config.get("api_key"):
            logger.warning(f"[VideoGenerator] 切换失败: 模型 {model_id} 未配置 API Key")
            return False
        
        self._current_model_id = model_id
        logger.info(f"[VideoGenerator] 已切换到模型: {model_id}")
        return True

    async def generate_video(
        self,
        prompt: str,
        image_url: Optional[str] = None,
        last_frame_url: Optional[str] = None,
        audio_url: Optional[str] = None,
        resolution: str = "720p",
        duration: int = 5,
        fps: int = 24,
        model_id: Optional[str] = None,
        **kwargs
    ) -> Tuple[bool, str, str]:
        """
        生成视频
        
        Returns:
            (是否成功, 任务ID或错误信息, 使用的模型ID)
        """
        use_model_id = model_id or self._current_model_id
        
        if use_model_id not in self._models_config:
            error_msg = f"模型 {use_model_id} 不存在"
            logger.error(f"[VideoGenerator] {error_msg}")
            return False, error_msg, ""
        
        model_config = self._models_config[use_model_id]
        if not isinstance(model_config, dict):
            error_msg = f"模型 {use_model_id} 配置无效"
            logger.error(f"[VideoGenerator] {error_msg}")
            return False, error_msg, ""
        
        model_name = model_config.get("model", "")
        
        # 检查图生视频支持
        if (image_url or last_frame_url) and not model_config.get("support_img2video", True):
            logger.warning(f"[VideoGenerator] 模型 {use_model_id} 不支持图生视频，将忽略图片")
            image_url = None
            last_frame_url = None
        
        provider = self._get_provider_instance(use_model_id)
        if not provider:
            error_msg = f"无法初始化模型 {use_model_id}"
            logger.error(f"[VideoGenerator] {error_msg}")
            return False, error_msg, ""

        # 合并默认参数
        final_resolution = resolution or model_config.get("default_resolution", "720p")
        final_duration = duration or model_config.get("default_duration", 5)
        prompt_extend = model_config.get("prompt_extend", True)
        watermark = model_config.get("watermark", False)

        try:
            # 日志记录模式
            if image_url and last_frame_url:
                mode = "首尾帧图生视频"
            elif image_url:
                mode = "首帧图生视频"
            elif last_frame_url:
                mode = "尾帧图生视频"
            else:
                mode = "文生视频"
            
            logger.info(f"[VideoGenerator] 提交任务: 模型={use_model_id}, 模式={mode}")
            
            task_id = await provider.create_task(
                model=model_name,
                prompt=prompt,
                image_url=image_url,
                last_frame_url=last_frame_url,
                audio_url=audio_url,
                resolution=final_resolution,
                duration=final_duration,
                fps=fps,
                prompt_extend=prompt_extend,
                watermark=watermark,
                **kwargs
            )
            
            logger.info(f"[VideoGenerator] 任务创建成功: {task_id}")
            return True, task_id, use_model_id
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[VideoGenerator] 创建任务失败: {error_msg}")
            import traceback
            traceback.print_exc()
            return False, error_msg, use_model_id

    async def get_task_status(self, task_id: str, model_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        if model_id not in self._models_config:
            return {"status": "error", "message": "模型不存在"}

        provider = self._get_provider_instance(model_id)
        if not provider:
            return {"status": "error", "message": "无法初始化服务商"}
            
        try:
            status = await provider.get_task_status(task_id)
            logger.debug(f"[VideoGenerator] 任务状态: {task_id} -> {status.get('status')}")
            return status
        except Exception as e:
            logger.error(f"[VideoGenerator] 获取状态失败: {e}")
            return {"status": "error", "message": str(e)}

    async def cancel_task(self, task_id: str, model_id: str) -> Tuple[bool, str]:
        """取消任务"""
        if model_id not in self._models_config:
            return False, "模型不存在"

        provider = self._get_provider_instance(model_id)
        if not provider:
            return False, "无法初始化服务商"
            
        try:
            return await provider.cancel_task(task_id)
        except Exception as e:
            logger.error(f"[VideoGenerator] 取消任务失败: {e}")
            return False, str(e)