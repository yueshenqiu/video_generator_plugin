"""预设模板管理模块"""

from typing import Dict, List, Optional, Any

from src.common.logger import get_logger

logger = get_logger("video_generator.template")


class TemplateManager:
    """预设模板管理器"""

    def __init__(self, templates: List[Dict[str, Any]]):
        self._templates: Dict[str, Dict[str, Any]] = {}
        self._load_templates(templates)

    def _load_templates(self, templates: List[Dict[str, Any]]) -> None:
        """加载模板配置"""
        if not templates:
            logger.info("[TemplateManager] 没有预设模板")
            return
            
        for template in templates:
            if not isinstance(template, dict):
                continue
                
            keyword = template.get("keyword", "").strip()
            if not keyword:
                continue
                
            keyword_lower = keyword.lower()
            self._templates[keyword_lower] = {
                "keyword": keyword,
                "description": template.get("description", ""),
                "prompt": template.get("prompt", ""),
                "resolution": template.get("resolution", "720p"),
                "fps": template.get("fps", 24),
                "duration": template.get("duration", 5),
            }
        
        logger.info(f"[TemplateManager] 已加载 {len(self._templates)} 个模板")

    def get_template(self, keyword: str) -> Optional[Dict[str, Any]]:
        """根据关键词获取模板"""
        if not keyword:
            return None
        return self._templates.get(keyword.lower().strip())

    def get_all_templates(self) -> Dict[str, Dict[str, Any]]:
        """获取所有模板"""
        return self._templates.copy()

    def add_template(self, keyword: str, template: Dict[str, Any]) -> bool:
        """添加新模板"""
        if not keyword:
            return False
            
        keyword_lower = keyword.lower().strip()
        self._templates[keyword_lower] = {
            "keyword": keyword.strip(),
            "description": template.get("description", ""),
            "prompt": template.get("prompt", ""),
            "resolution": template.get("resolution", "720p"),
            "fps": template.get("fps", 24),
            "duration": template.get("duration", 5),
        }
        logger.info(f"[TemplateManager] 添加模板: {keyword}")
        return True

    def remove_template(self, keyword: str) -> bool:
        """删除模板"""
        if not keyword:
            return False
        keyword_lower = keyword.lower().strip()
        if keyword_lower in self._templates:
            del self._templates[keyword_lower]
            logger.info(f"[TemplateManager] 删除模板: {keyword}")
            return True
        return False

    def has_template(self, keyword: str) -> bool:
        """检查模板是否存在"""
        if not keyword:
            return False
        return keyword.lower().strip() in self._templates

    def get_keywords(self) -> List[str]:
        """获取所有关键词"""
        return [t["keyword"] for t in self._templates.values()]

    def get_template_count(self) -> int:
        """获取模板数量"""
        return len(self._templates)