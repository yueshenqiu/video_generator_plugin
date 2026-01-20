"""图片工具模块"""

import base64
from typing import Optional, List, Any

from src.common.logger import get_logger

logger = get_logger("video_generator.image")


class ImageProcessor:
    """图片处理器"""

    def __init__(self, command_instance):
        self._command = command_instance

    def _get_chat_stream(self) -> Optional[Any]:
        """获取chat_stream"""
        try:
            if hasattr(self._command, 'message') and hasattr(self._command.message, 'chat_stream'):
                return self._command.message.chat_stream
            return None
        except Exception:
            return None

    def _get_chat_id(self) -> Optional[str]:
        """获取chat_id"""
        chat_stream = self._get_chat_stream()
        if chat_stream and hasattr(chat_stream, 'stream_id'):
            return chat_stream.stream_id
        return None

    async def get_recent_images(self, count: int = 1) -> List[str]:
        """获取最近的图片URL列表"""
        all_images = []
        
        try:
            logger.debug(f"[ImageProcessor] 获取最近 {count} 张图片")
            
            # 来源1：当前消息
            current = self._get_images_from_current_message()
            all_images.extend(current)
            
            if len(all_images) >= count:
                return all_images[:count]
            
            # 来源2：message_recv
            recv = self._get_images_from_message_recv()
            for img in recv:
                if img not in all_images:
                    all_images.append(img)
            
            if len(all_images) >= count:
                return all_images[:count]
            
            # 来源3：历史消息
            history = await self._get_images_from_history(count - len(all_images))
            for img in history:
                if img not in all_images:
                    all_images.append(img)
            
            if all_images:
                logger.info(f"[ImageProcessor] 获取到 {len(all_images)} 张图片")
            else:
                logger.warning("[ImageProcessor] 未找到图片")
            
            return all_images[:count]
            
        except Exception as e:
            logger.error(f"[ImageProcessor] 获取图片失败: {e}")
            return []

    async def get_recent_image_url(self) -> Optional[str]:
        """获取最近的单张图片URL"""
        images = await self.get_recent_images(count=1)
        return images[0] if images else None

    def _get_images_from_current_message(self) -> List[str]:
        """从当前消息获取图片"""
        try:
            if not hasattr(self._command, 'message'):
                return []
            
            message = self._command.message
            if not hasattr(message, 'message_segment'):
                return []
            
            segments = message.message_segment
            if not segments:
                return []
            
            data_list = self._extract_images_from_segments(segments)
            return [self._convert_to_url(img) for img in data_list if img]
            
        except Exception as e:
            logger.debug(f"[ImageProcessor] 当前消息: {e}")
            return []

    def _get_images_from_message_recv(self) -> List[str]:
        """从message_recv获取图片"""
        try:
            if not hasattr(self._command, 'message'):
                return []
            
            message = self._command.message
            if not hasattr(message, 'message_recv'):
                return []
            
            recv = message.message_recv
            if not recv or not hasattr(recv, 'message_segment'):
                return []
            
            segments = recv.message_segment
            if not segments:
                return []
            
            data_list = self._extract_images_from_segments(segments)
            return [self._convert_to_url(img) for img in data_list if img]
            
        except Exception as e:
            logger.debug(f"[ImageProcessor] message_recv: {e}")
            return []

    async def _get_images_from_history(self, count: int = 1) -> List[str]:
        """从历史消息获取图片"""
        try:
            from src.plugin_system.apis import message_api
            import time
            
            chat_id = self._get_chat_id()
            if not chat_id:
                return []
            
            current_time = time.time()
            messages = message_api.get_messages_by_time_in_chat(
                chat_id=chat_id,
                start_time=current_time - 300,
                end_time=current_time,
                limit=30,
                limit_mode="latest"
            )
            
            if not messages:
                return []
            
            result = []
            
            for msg in messages:
                if len(result) >= count:
                    break
                
                is_picid = getattr(msg, 'is_picid', False)
                if not is_picid:
                    continue
                
                segment = getattr(msg, 'message_segment', None)
                if not segment:
                    continue
                
                data_list = self._extract_images_from_segments(segment)
                for img in data_list:
                    if img and len(result) < count:
                        url = self._convert_to_url(img)
                        if url and url not in result:
                            result.append(url)
            
            return result
            
        except Exception as e:
            logger.error(f"[ImageProcessor] 历史消息: {e}")
            return []

    def _extract_images_from_segments(self, segments) -> List[str]:
        """从消息段提取图片"""
        result = []

        try:
            try:
                from maim_message import Seg
                if isinstance(segments, Seg):
                    return self._extract_from_single_seg(segments)
            except ImportError:
                pass
            
            if hasattr(segments, 'type'):
                return self._extract_from_single_seg(segments)

            if isinstance(segments, (list, tuple)):
                for seg in segments:
                    result.extend(self._extract_from_single_seg(seg))

            return result

        except Exception as e:
            logger.debug(f"[ImageProcessor] 提取失败: {e}")
            return result

    def _extract_from_single_seg(self, seg) -> List[str]:
        """从单个seg提取图片"""
        result = []
        
        try:
            seg_type = getattr(seg, 'type', None)
            seg_data = getattr(seg, 'data', None)

            if seg_type in ('image', 'emoji'):
                if seg_data:
                    extracted = self._extract_image_data(seg_data)
                    if extracted:
                        result.append(extracted)

            elif seg_type == 'seglist':
                if seg_data and isinstance(seg_data, (list, tuple)):
                    for sub in seg_data:
                        result.extend(self._extract_from_single_seg(sub))

        except Exception as e:
            logger.debug(f"[ImageProcessor] seg提取: {e}")

        return result

    def _extract_image_data(self, seg_data) -> Optional[str]:
        """从seg.data提取图片数据"""
        try:
            if isinstance(seg_data, str):
                return seg_data
            
            elif isinstance(seg_data, dict):
                url = seg_data.get('url') or seg_data.get('file') or seg_data.get('path')
                if url:
                    return url
                
                b64 = seg_data.get('base64') or seg_data.get('data')
                if b64:
                    return b64
            
            elif isinstance(seg_data, bytes):
                return base64.b64encode(seg_data).decode('utf-8')
                
        except Exception:
            pass
        
        return None

    def _convert_to_url(self, image_data: str) -> str:
        """转换为URL格式"""
        if not image_data:
            return ""

        if image_data.startswith(('http://', 'https://')):
            return image_data

        if image_data.startswith('data:image/'):
            return image_data

        fmt = self._detect_format(image_data)
        return f"data:image/{fmt};base64,{image_data}"

    def _detect_format(self, b64_data: str) -> str:
        """检测图片格式"""
        try:
            if b64_data.startswith('/9j/'):
                return 'jpeg'
            elif b64_data.startswith('iVBOR'):
                return 'png'
            elif b64_data.startswith('R0lGO'):
                return 'gif'
            elif b64_data.startswith('UklGR'):
                return 'webp'
            
            try:
                decoded = base64.b64decode(b64_data[:32])
                if decoded.startswith(b'\xff\xd8\xff'):
                    return 'jpeg'
                elif decoded.startswith(b'\x89PNG'):
                    return 'png'
                elif decoded.startswith(b'GIF8'):
                    return 'gif'
            except Exception:
                pass

            return 'png'
        except Exception:
            return 'png'