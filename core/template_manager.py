"""预设模板管理模块"""

import logging
from typing import Dict, List, Optional, Any


class TemplateManager:
    """预设模板管理器"""

    def __init__(
        self,
        templates: List[Dict[str, Any]],
        logger: Optional[logging.Logger] = None,
    ):
        self._logger = logger or logging.getLogger("video_generator.template")
        self._templates: Dict[str, Dict[str, Any]] = {}
        self._load_templates(templates)

    def _load_templates(self, templates: List[Dict[str, Any]]) -> None:
        if not templates:
            self._logger.info("[TemplateManager] 没有预设模板")
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
        
        self._logger.debug(f"[TemplateManager] 已加载 {len(self._templates)} 个模板")

    def get_template(self, keyword: str) -> Optional[Dict[str, Any]]:
        if not keyword:
            return None
        return self._templates.get(keyword.lower().strip())

    def get_all_templates(self) -> Dict[str, Dict[str, Any]]:
        return self._templates.copy()

    def add_template(self, keyword: str, template: Dict[str, Any]) -> bool:
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
        self._logger.info(f"[TemplateManager] 添加模板: {keyword}")
        return True

    def remove_template(self, keyword: str) -> bool:
        if not keyword:
            return False
        keyword_lower = keyword.lower().strip()
        if keyword_lower in self._templates:
            del self._templates[keyword_lower]
            self._logger.info(f"[TemplateManager] 删除模板: {keyword}")
            return True
        return False

    def has_template(self, keyword: str) -> bool:
        if not keyword:
            return False
        return keyword.lower().strip() in self._templates

    def get_keywords(self) -> List[str]:
        return [t["keyword"] for t in self._templates.values()]

    def get_template_count(self) -> int:
        return len(self._templates)