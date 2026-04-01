"""可灵视频生成服务商"""

import asyncio
import json
from typing import Dict, Any, Optional, Tuple
from urllib import request, error

from src.common.logger import get_logger

from .base import BaseProvider

logger = get_logger("video_generator.provider.kling")


class KlingProvider(BaseProvider):
    """可灵 API Provider（最小闭环：text2video/image2video + query）"""

    PROVIDER_NAME = "kling"

    def __init__(self, api_key: str, base_url: str = ""):
        super().__init__(api_key=api_key, base_url=base_url)
        self._base_url = (base_url or "https://api-beijing.klingai.com").rstrip("/")
        # 记录任务类型，便于查询时路由到正确 endpoint
        self._task_type_map: Dict[str, str] = {}

    # -------------------- HTTP --------------------

    async def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await asyncio.to_thread(self._request_sync, method, path, payload)

    def _request_sync(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self._base_url}{path}"
        data = None
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = request.Request(url=url, data=data, headers=headers, method=method.upper())

        try:
            with request.urlopen(req, timeout=90) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except error.HTTPError as e:
            try:
                body = e.read().decode("utf-8")
                parsed = json.loads(body) if body else {}
            except Exception:
                parsed = {}
            if not isinstance(parsed, dict):
                parsed = {}
            parsed.setdefault("code", e.code)
            parsed.setdefault("message", f"HTTPError {e.code}")
            return parsed
        except error.URLError as e:
            return {"code": -1, "message": f"网络错误: {e}"}
        except Exception as e:
            return {"code": -1, "message": str(e)}

    # -------------------- 参数处理 --------------------

    @staticmethod
    def _map_status(status: str) -> str:
        mapping = {
            "submitted": "queued",
            "processing": "running",
            "succeed": "succeeded",
            "failed": "failed",
        }
        return mapping.get(status, "running")

    @staticmethod
    def _map_progress(status: str) -> int:
        mapping = {
            "submitted": 5,
            "processing": 50,
            "succeed": 100,
            "failed": 100,
        }
        return mapping.get(status, 30)

    @staticmethod
    def _normalize_duration(duration: int) -> str:
        # text2video/image2video 常见支持 5/10，最小实现做就近降级
        return "5" if duration <= 7 else "10"

    @staticmethod
    def _resolution_to_aspect_ratio(resolution: str) -> str:
        """
        把你们现有 resolution 参数映射到可灵的 aspect_ratio（仅文生使用）
        - 720p/1080p/4k -> 16:9
        - 自定义宽高 -> 按宽高比映射
        """
        if not resolution:
            return "16:9"

        r = resolution.lower().strip()
        if r in {"720p", "1080p", "4k", "480p"}:
            return "16:9"

        # 支持 1080x1920
        if "x" in r:
            try:
                w_str, h_str = r.split("x", 1)
                w = int(w_str)
                h = int(h_str)
                if w > 0 and h > 0:
                    ratio = w / h
                    if ratio > 1.2:
                        return "16:9"
                    if ratio < 0.8:
                        return "9:16"
                    return "1:1"
            except Exception:
                return "16:9"

        return "16:9"

    # -------------------- BaseProvider 实现 --------------------

    async def create_task(
        self,
        model: str,
        prompt: str,
        image_url: Optional[str] = None,
        last_frame_url: Optional[str] = None,
        audio_url: Optional[str] = None,
        resolution: str = "720p",
        duration: int = 5,
        fps: int = 24,
        **kwargs
    ) -> str:
        """
        创建任务：
        - 文生：/v1/videos/text2video
        - 图生：/v1/videos/image2video
        """
        if not prompt:
            raise ValueError("提示词不能为空")

        mode = str(kwargs.get("mode", "pro")).lower()
        if mode not in {"std", "pro"}:
            mode = "pro"

        watermark = bool(kwargs.get("watermark", False))
        normalized_duration = self._normalize_duration(duration)

        is_img2video = bool(image_url or last_frame_url)

        if is_img2video:
            endpoint = "/v1/videos/image2video"
            payload: Dict[str, Any] = {
                "model_name": model,
                "prompt": prompt,
                "duration": normalized_duration,
                "mode": mode,
                "watermark_info": {"enabled": watermark},
            }
            if image_url:
                payload["image"] = image_url
            if last_frame_url:
                payload["image_tail"] = last_frame_url
        else:
            endpoint = "/v1/videos/text2video"
            payload = {
                "model_name": model,
                "prompt": prompt,
                "duration": normalized_duration,
                "mode": mode,
                "aspect_ratio": self._resolution_to_aspect_ratio(resolution),
                "watermark_info": {"enabled": watermark},
            }

        # 可选参数（仅在有值时透传）
        negative_prompt = kwargs.get("negative_prompt")
        if isinstance(negative_prompt, str) and negative_prompt.strip():
            payload["negative_prompt"] = negative_prompt.strip()

        external_task_id = kwargs.get("external_task_id")
        if isinstance(external_task_id, str) and external_task_id.strip():
            payload["external_task_id"] = external_task_id.strip()

        callback_url = kwargs.get("callback_url")
        if isinstance(callback_url, str) and callback_url.strip():
            payload["callback_url"] = callback_url.strip()

        # sound 仅 v2.6+ 支持，这里做最小兼容：仅模型名含 v2-6 时附带
        music_enabled = bool(kwargs.get("music_enabled", False))
        if "kling-v2-6" in (model or ""):
            payload["sound"] = "on" if music_enabled else "off"

        logger.info(f"[Kling] create_task endpoint={endpoint}, model={model}")

        resp = await self._request("POST", endpoint, payload)
        code = resp.get("code")
        if code != 0:
            msg = resp.get("message", "创建任务失败")
            raise RuntimeError(f"可灵创建任务失败: {msg}")

        data = resp.get("data") or {}
        task_id = data.get("task_id")
        if not task_id:
            raise RuntimeError("可灵返回 task_id 为空")

        self._task_type_map[task_id] = "image2video" if is_img2video else "text2video"
        return task_id

    async def _query_task(self, endpoint: str, task_id: str) -> Dict[str, Any]:
        resp = await self._request("GET", f"{endpoint}/{task_id}", None)
        return resp

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        返回统一状态结构：
        {
            status: queued/running/succeeded/failed/error
            progress: int
            video_url: str
            message: str
        }
        """
        task_type = self._task_type_map.get(task_id)

        endpoints = []
        if task_type == "text2video":
            endpoints.append("/v1/videos/text2video")
        elif task_type == "image2video":
            endpoints.append("/v1/videos/image2video")
        else:
            # 兜底尝试
            endpoints.extend([
                "/v1/videos/text2video",
                "/v1/videos/image2video",
            ])

        last_error = "任务不存在或查询失败"

        for ep in endpoints:
            resp = await self._query_task(ep, task_id)
            code = resp.get("code", -1)
            if code != 0:
                last_error = resp.get("message", last_error)
                continue

            data = resp.get("data") or {}
            raw_status = data.get("task_status", "")
            status = self._map_status(raw_status)
            progress = self._map_progress(raw_status)

            result = data.get("task_result") or {}
            videos = result.get("videos") or []
            video_url = ""
            if videos and isinstance(videos, list):
                first = videos[0] or {}
                video_url = first.get("url", "") or first.get("watermark_url", "")

            msg = data.get("task_status_msg", "") or resp.get("message", "")

            return {
                "status": status,
                "progress": progress,
                "video_url": video_url,
                "message": msg,
            }

        return {
            "status": "error",
            "progress": 0,
            "video_url": "",
            "message": f"可灵查询失败: {last_error}",
        }

    async def cancel_task(self, task_id: str) -> Tuple[bool, str]:
        """
        可灵文档未提供统一 cancel 接口（当前最小接入）。
        """
        return False, "可灵服务商暂不支持远端取消任务（可取消本地排队任务）"