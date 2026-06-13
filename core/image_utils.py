"""图片工具模块 - 从消息中提取图片（当前消息 → 引用 → NapCat历史 → SDK历史）"""

import base64
import logging
from pathlib import Path
from typing import Optional, List, Any

import aiohttp


class ImageProcessor:
    """图片处理器 - 从命令消息中获取图片

    优先级：
    1. 当前消息中直接附带的图片
    2. 引用（回复）消息中的图片（包括合并转发消息）
    3. NapCat 适配器获取最近消息中的图片
    4. SDK message.get_recent 获取历史图片
    """

    def __init__(self, ctx, stream_id: str, kwargs: dict = None, logger: Optional[logging.Logger] = None):
        self._ctx = ctx
        self._stream_id = stream_id
        self._kwargs = kwargs or {}
        self._logger = logger or (ctx.logger if hasattr(ctx, 'logger') else logging.getLogger("video_generator.image"))

    def _get_message_dict(self) -> dict:
        message = self._kwargs.get("message", {})
        return message if isinstance(message, dict) else {}

    def _extract_session_info(self) -> dict:
        message = self._get_message_dict()
        msg_info = message.get("message_info", {}) or {}
        group_info = msg_info.get("group_info") or {}
        user_info = msg_info.get("user_info") or {}
        platform = str(message.get("platform", "") or "qq")

        chat_type = ""
        chat_id = ""
        if group_info and group_info.get("group_id"):
            chat_type = "group"
            chat_id = str(group_info["group_id"])
        elif user_info and user_info.get("user_id"):
            chat_type = "private"
            chat_id = str(user_info["user_id"])

        return {
            "platform": platform,
            "chat_type": chat_type,
            "chat_id": chat_id,
            "user_id": str(user_info.get("user_id", "") if isinstance(user_info, dict) else ""),
        }

    async def get_recent_images(self, count: int = 1) -> List[str]:
        """按优先级获取图片"""
        all_images: List[str] = []

        # 1. 当前消息中的图片
        current_images = self._extract_from_current_message()
        for img in current_images:
            if img and img not in all_images:
                all_images.append(img)
                if len(all_images) >= count:
                    break

        if len(all_images) >= count:
            self._logger.info(f"[ImageProcessor] 从当前消息获取到 {len(all_images)} 张图片")
            return await self._convert_images(all_images[:count])

        # 2. 引用消息中的图片（包括合并转发）
        reply_images = await self._extract_from_reply(count)
        for img in reply_images:
            if img and img not in all_images:
                all_images.append(img)
                if len(all_images) >= count:
                    break

        if len(all_images) >= count:
            self._logger.info(f"[ImageProcessor] 从引用消息获取到 {len(all_images)} 张图片")
            return await self._convert_images(all_images[:count])

        # 3. NapCat 适配器获取最近消息
        napcat_images = await self._extract_from_napcat_history(count - len(all_images))
        for img in napcat_images:
            if img and img not in all_images:
                all_images.append(img)
                if len(all_images) >= count:
                    break

        if len(all_images) >= count:
            self._logger.info(f"[ImageProcessor] 从NapCat历史获取到图片")
            return await self._convert_images(all_images[:count])

        # 4. SDK message.get_recent 回退
        sdk_images = await self._extract_from_sdk_history(count - len(all_images))
        for img in sdk_images:
            if img and img not in all_images:
                all_images.append(img)
                if len(all_images) >= count:
                    break

        if all_images:
            self._logger.info(f"[ImageProcessor] 总共获取到 {len(all_images)} 张图片")
            return await self._convert_images(all_images[:count])

        self._logger.warning("[ImageProcessor] 未找到任何图片")
        return []

    async def get_recent_image_url(self) -> Optional[str]:
        images = await self.get_recent_images(count=1)
        return images[0] if images else None

    # ==================== 来源1: 当前消息 ====================

    def _extract_from_current_message(self) -> List[str]:
        message = self._get_message_dict()
        raw_msg = message.get("raw_message", message.get("message", []))
        if not isinstance(raw_msg, list):
            return []

        results = []
        for seg in raw_msg:
            if not isinstance(seg, dict):
                continue
            if seg.get("type") == "image":
                url = self._extract_image_url_from_segment(seg)
                if url:
                    results.append(url)
        return results

    # ==================== 来源2: 引用消息 ====================

    async def _extract_from_reply(self, count: int = 1) -> List[str]:
        message = self._get_message_dict()
        results = []

        # 检查 raw_message 中的 reply segment，追溯目标消息
        raw_msg = message.get("raw_message", message.get("message", []))
        if not isinstance(raw_msg, list):
            return results

        for seg in raw_msg:
            if not isinstance(seg, dict) or seg.get("type") != "reply":
                continue
            reply_data = seg.get("data", {})
            if not isinstance(reply_data, dict):
                continue
            target_id = str(
                reply_data.get("target_message_id")
                or reply_data.get("id")
                or reply_data.get("message_id")
                or ""
            ).strip()
            if not target_id:
                continue

            self._logger.info(f"[ImageProcessor] 追溯回复目标消息: {target_id}")

            # 通过 NapCat get_msg 获取被引用消息
            try:
                napcat_result = await self._ctx.api.call(
                    "adapter.napcat.message.get_msg",
                    message_id=int(target_id),
                )
                target_msg = self._extract_napcat_msg(napcat_result)
                if target_msg:
                    msg_segs = target_msg.get("message", target_msg.get("raw_message", []))
                    seg_types = [s.get("type", "?") for s in msg_segs if isinstance(s, dict)] if isinstance(msg_segs, list) else []
                    self._logger.info(f"[ImageProcessor] get_msg 返回 seg_types={seg_types}")

                    # 检查是否是合并转发消息
                    if isinstance(msg_segs, list):
                        is_forward = any(
                            isinstance(s, dict) and s.get("type") == "forward"
                            for s in msg_segs
                        )
                        if is_forward:
                            self._logger.info("[ImageProcessor] 检测到合并转发消息，提取子消息图片")
                            forward_images = await self._extract_from_forward_message(target_id, count)
                            if forward_images:
                                return forward_images

                    # 普通消息：直接提取图片
                    images = await self._resolve_images_from_napcat_msg(target_msg, count)
                    if images:
                        self._logger.info(f"[ImageProcessor] 从 NapCat get_msg 获取到 {len(images)} 张引用图片")
                        return images

                    # 如果 get_msg 没能获取到有效图片，尝试当作合并转发处理
                    self._logger.info("[ImageProcessor] 普通提取无有效图片，尝试 get_forward_msg")
                    forward_images = await self._extract_from_forward_message(target_id, count)
                    if forward_images:
                        return forward_images
                else:
                    self._logger.info("[ImageProcessor] get_msg 返回空消息体")
            except Exception as e:
                self._logger.info(f"[ImageProcessor] NapCat get_msg 失败: {e}")

            # SDK 回退
            try:
                sdk_result = await self._ctx.message.get_by_id(message_id=target_id)
                if isinstance(sdk_result, dict):
                    inner = sdk_result.get("result", sdk_result)
                    if isinstance(inner, dict):
                        target_msg_data = inner.get("message", inner)
                        if isinstance(target_msg_data, dict):
                            images = self._extract_images_from_message_dict(target_msg_data)
                            if images:
                                self._logger.info(f"[ImageProcessor] SDK get_by_id 获取到 {len(images)} 张, 前缀: {images[0][:30]}...")
                                # 过滤无效图片数据
                                valid_images = [img for img in images if self._is_valid_image_data(img)]
                                if valid_images:
                                    return valid_images[:count]
                                else:
                                    self._logger.info("[ImageProcessor] SDK 返回的图片数据无效（可能是描述文本），跳过")
            except Exception as e:
                self._logger.debug(f"[ImageProcessor] SDK get_by_id 失败: {e}")

        return results

    # ==================== 合并转发消息处理 ====================

    async def _extract_from_forward_message(self, message_id: str, count: int = 2) -> List[str]:
        """从合并转发消息中提取图片，按子消息顺序返回"""
        try:
            forward_result = await self._ctx.api.call(
                "adapter.napcat.message.get_forward_msg",
                message_id=message_id,
            )
            messages = self._extract_forward_messages(forward_result)
            if not messages:
                self._logger.debug("[ImageProcessor] 合并转发消息中无子消息")
                return []

            self._logger.info(f"[ImageProcessor] 合并转发包含 {len(messages)} 条子消息")

            all_images = []
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                segs = msg.get("message", msg.get("content", msg.get("raw_message", [])))
                if not isinstance(segs, list):
                    continue
                for seg in segs:
                    if not isinstance(seg, dict) or seg.get("type") != "image":
                        continue
                    # 合并转发里优先用 URL 下载（get_image 对转发内图片常超时）
                    img = await self._resolve_forward_image(seg)
                    if img:
                        all_images.append(img)
                        if len(all_images) >= count:
                            self._logger.info(f"[ImageProcessor] 从合并转发获取到 {len(all_images)} 张图片")
                            return all_images

            if all_images:
                self._logger.info(f"[ImageProcessor] 从合并转发获取到 {len(all_images)} 张图片")
            return all_images

        except Exception as e:
            self._logger.warning(f"[ImageProcessor] 获取合并转发内容失败: {e}")
            return []

    async def _resolve_forward_image(self, seg: dict) -> Optional[str]:
        """从合并转发的 image segment 获取图片，优先 URL 下载（跳过 get_image 避免超时）"""
        data = seg.get("data", "")
        if isinstance(data, dict):
            # 已有 base64
            file_data = str(data.get("file") or "")
            if file_data.startswith("base64://"):
                return file_data[len("base64://"):]
            # 优先 URL 下载（合并转发里 get_image 常超时）
            url = data.get("url") or ""
            if url and str(url).startswith(("http://", "https://")):
                downloaded = await self._download_image_as_base64(str(url))
                if downloaded:
                    return downloaded
            # 回退 get_image
            if file_data:
                resolved = await self._resolve_napcat_file(file_data)
                if resolved:
                    return resolved
        elif isinstance(data, str) and data:
            if self._is_valid_image_data(data):
                return data
        return None

    def _extract_forward_messages(self, result: Any) -> list:
        """从 get_forward_msg 响应中提取子消息列表"""
        if isinstance(result, list):
            return result
        if not isinstance(result, dict):
            return []
        # 可能嵌套 {"result": {"messages": [...]}} 或 {"messages": [...]}
        inner = result.get("result", result)
        if isinstance(inner, dict):
            msgs = inner.get("messages", inner.get("data", []))
            if isinstance(msgs, dict):
                msgs = msgs.get("messages", [])
            if isinstance(msgs, list):
                return msgs
        if isinstance(inner, list):
            return inner
        return []

    # ==================== 来源3: NapCat 适配器历史 ====================

    async def _extract_from_napcat_history(self, count: int = 1) -> List[str]:
        info = self._extract_session_info()
        results = []

        try:
            if info["chat_type"] == "group" and info["chat_id"]:
                result = await self._ctx.api.call(
                    "adapter.napcat.message.get_group_msg_history",
                    params={"group_id": int(info["chat_id"]), "count": 30},
                )
                messages = self._parse_napcat_messages(result)
            elif info["chat_type"] == "private" and info["chat_id"]:
                result = await self._ctx.api.call(
                    "adapter.napcat.message.get_friend_msg_history",
                    params={"user_id": int(info["chat_id"]), "count": 30},
                )
                messages = self._parse_napcat_messages(result)
            else:
                return results

            for msg in reversed(messages):
                if not isinstance(msg, dict):
                    continue
                segs = msg.get("message", msg.get("raw_message", []))
                if not isinstance(segs, list):
                    continue
                for seg in segs:
                    if not isinstance(seg, dict) or seg.get("type") != "image":
                        continue
                    img = await self._resolve_single_napcat_image(seg)
                    if img:
                        results.append(img)
                        if len(results) >= count:
                            return results
        except Exception as e:
            self._logger.debug(f"[ImageProcessor] NapCat历史获取失败: {e}")

        return results

    # ==================== 来源4: SDK 历史回退 ====================

    async def _extract_from_sdk_history(self, count: int = 1) -> List[str]:
        results = []
        try:
            raw_result = await self._ctx.message.get_recent(
                chat_id=self._stream_id,
                limit=30,
            )

            if isinstance(raw_result, dict) and raw_result.get("success"):
                inner = raw_result.get("result", {})
                if isinstance(inner, dict) and inner.get("success"):
                    messages = inner.get("messages", [])
                else:
                    messages = []
            elif isinstance(raw_result, list):
                messages = raw_result
            else:
                messages = []

            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                images = self._extract_images_from_message_dict(msg)
                for img in images:
                    if img and img not in results:
                        results.append(img)
                        if len(results) >= count:
                            return results
        except Exception as e:
            self._logger.debug(f"[ImageProcessor] SDK历史获取失败: {e}")

        return results

    # ==================== NapCat 图片解析 ====================

    async def _resolve_images_from_napcat_msg(self, msg: dict, count: int = 1) -> List[str]:
        """从 NapCat 格式的消息字典中提取多张图片"""
        segs = msg.get("message", msg.get("raw_message", []))
        if not isinstance(segs, list):
            return []
        results = []
        for seg in segs:
            if not isinstance(seg, dict) or seg.get("type") != "image":
                continue
            img = await self._resolve_single_napcat_image(seg)
            if img:
                results.append(img)
                if len(results) >= count:
                    break
        return results

    async def _resolve_single_napcat_image(self, seg: dict) -> Optional[str]:
        """从单个 NapCat image segment 解析出图片数据"""
        data = seg.get("data", "")
        if isinstance(data, dict):
            file_data = str(data.get("file") or "")
            if file_data.startswith("base64://"):
                return file_data[len("base64://"):]
            # 优先通过 get_image 获取本地文件
            if file_data:
                resolved = await self._resolve_napcat_file(file_data)
                if resolved:
                    return resolved
            # 回退：下载 URL 转 base64
            url = data.get("url") or ""
            if url and str(url).startswith(("http://", "https://")):
                downloaded = await self._download_image_as_base64(str(url))
                if downloaded:
                    return downloaded
                return str(url)
        elif isinstance(data, str) and data:
            # 过滤掉非图片数据（如 MaiBot 的图片描述文本）
            if self._is_valid_image_data(data):
                return data
            else:
                self._logger.debug(f"[ImageProcessor] 跳过非图片数据: {data[:40]}...")
                return None
        return None

    def _is_valid_image_data(self, data: str) -> bool:
        """判断字符串是否是有效的图片数据（URL/base64），排除文字描述"""
        if not data:
            return False
        if data.startswith(("http://", "https://", "data:image/", "base64://")):
            return True
        # base64 图片数据通常很长且以特定前缀开头
        if len(data) > 200 and data[:4] in ("/9j/", "iVBO", "R0lG", "UklG"):
            return True
        # 太短或包含中文字符的不是图片
        if len(data) < 200:
            return False
        # 检查是否主要由 base64 字符组成
        import re
        if re.match(r'^[A-Za-z0-9+/=\s]+$', data[:100]):
            return True
        return False

    async def _resolve_napcat_file(self, file_data: str) -> Optional[str]:
        """通过 NapCat get_image API 解析文件引用"""
        try:
            img_result = await self._ctx.api.call(
                "adapter.napcat.file.get_image",
                params={"file": file_data},
            )
            if not isinstance(img_result, dict):
                return None
            napcat_resp = img_result.get("result", img_result)
            if not isinstance(napcat_resp, dict):
                napcat_resp = img_result
            inner = napcat_resp.get("data", {})
            if isinstance(inner, dict):
                file_or_url = str(inner.get("file") or inner.get("url") or "")
            elif isinstance(inner, str):
                file_or_url = inner
            else:
                return None

            if file_or_url.startswith("base64://"):
                return file_or_url[len("base64://"):]
            if file_or_url and not file_or_url.startswith(("http://", "https://")):
                img_path = Path(file_or_url)
                if img_path.exists():
                    self._logger.info(f"[ImageProcessor] 本地文件: {file_or_url}")
                    return base64.b64encode(img_path.read_bytes()).decode("utf-8")
            if file_or_url.startswith(("http://", "https://")):
                downloaded = await self._download_image_as_base64(file_or_url)
                if downloaded:
                    return downloaded
                return file_or_url
        except Exception as e:
            self._logger.warning(f"[ImageProcessor] get_image 失败: {e}")
        return None

    # ==================== 图片转换 ====================

    async def _convert_images(self, images: List[str]) -> List[str]:
        """确保图片是 data URI 格式"""
        converted = []
        for img in images:
            converted.append(await self._ensure_data_uri(img))
        return converted

    async def _ensure_data_uri(self, url: str) -> str:
        if not url:
            return url
        if url.startswith("data:"):
            return url
        if not url.startswith(("http://", "https://")):
            fmt = self._detect_format(url)
            return f"data:image/{fmt};base64,{url}"
        # URL → 下载转 data URI
        downloaded = await self._download_image_as_base64(url)
        if downloaded:
            fmt = self._detect_format(downloaded)
            return f"data:image/{fmt};base64,{downloaded}"
        return url

    async def _download_image_as_base64(self, url: str) -> Optional[str]:
        """下载图片 URL 转为 base64"""
        if not url or not url.startswith(("http://", "https://")):
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        self._logger.warning(f"[ImageProcessor] 下载图片失败 HTTP {resp.status}")
                        return None
                    data = await resp.read()
                    if not data:
                        return None
                    return base64.b64encode(data).decode("utf-8")
        except Exception as e:
            self._logger.warning(f"[ImageProcessor] 下载图片异常: {e}")
            return None

    # ==================== 通用辅助 ====================

    def _extract_napcat_msg(self, result: Any) -> Optional[dict]:
        """从 NapCat get_msg 响应中提取消息体"""
        if not isinstance(result, dict):
            return None
        inner = result.get("result", result)
        if not isinstance(inner, dict):
            return None
        data = inner.get("data", inner)
        if isinstance(data, dict):
            return data
        return inner

    def _parse_napcat_messages(self, result: Any) -> list:
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            inner = result.get("result", result)
            if isinstance(inner, dict):
                msgs = inner.get("data", inner.get("messages", []))
                if isinstance(msgs, dict):
                    msgs = msgs.get("messages", [])
                return msgs if isinstance(msgs, list) else []
            if isinstance(inner, list):
                return inner
        return []

    def _extract_images_from_message_dict(self, msg: dict) -> List[str]:
        results = []
        segments = msg.get("raw_message", msg.get("message_segment", msg.get("message", [])))
        if isinstance(segments, list):
            for seg in segments:
                if isinstance(seg, dict) and seg.get("type") == "image":
                    url = self._extract_image_url_from_segment(seg)
                    if url:
                        results.append(url)
        elif isinstance(segments, dict):
            if segments.get("type") in ("image", "imageurl"):
                content = segments.get("content") or (segments.get("data", {}) or {}).get("content", "")
                if content:
                    results.append(str(content))
            elif segments.get("type") == "seglist":
                for child in segments.get("data", []) or []:
                    if isinstance(child, dict) and child.get("type") in ("image", "imageurl"):
                        content = child.get("content") or (child.get("data", {}) or {}).get("content", "")
                        if content:
                            results.append(str(content))
        return results

    def _extract_image_url_from_segment(self, seg: dict) -> Optional[str]:
        data = seg.get("data", "")
        if isinstance(data, dict):
            url = data.get("url") or data.get("file") or data.get("path") or data.get("base64") or ""
            if url:
                return str(url)
            b64 = data.get("binary_data_base64")
            if b64:
                return str(b64)
        elif isinstance(data, str) and data:
            return data
        b64 = seg.get("binary_data_base64")
        if b64 and isinstance(b64, str):
            return b64
        return None

    def _detect_format(self, b64_data: str) -> str:
        try:
            if b64_data.startswith("/9j/"):
                return "jpeg"
            elif b64_data.startswith("iVBOR"):
                return "png"
            elif b64_data.startswith("R0lGO"):
                return "gif"
            elif b64_data.startswith("UklGR"):
                return "webp"
        except Exception:
            pass
        return "png"
