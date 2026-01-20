"""视频下载模块 - 支持断点续传"""

import asyncio
import aiohttp
import aiofiles
from datetime import datetime
from typing import Optional, Tuple, List, Callable
from pathlib import Path

from src.common.logger import get_logger

logger = get_logger("video_generator.downloader")


class VideoDownloader:
    """
    视频下载器 - 支持断点续传
    
    特性：
    - 断点续传：下载中断后可从断点继续
    - 进度回调：可获取下载进度
    - 自动清理：限制临时文件数量
    - 超时控制：防止下载卡死
    """

    MAX_VIDEO_FILES = 10
    CHUNK_SIZE = 8192
    TEMP_SUFFIX = ".tmp"

    def __init__(self, save_dir: Optional[str] = None, timeout: int = 300):
        """
        初始化下载器
        
        Args:
            save_dir: 保存目录
            timeout: 下载超时时间（秒）
        """
        if save_dir:
            self._save_dir = Path(save_dir)
        else:
            self._save_dir = Path(__file__).parent.parent / "temp"
        
        self._save_dir.mkdir(parents=True, exist_ok=True)
        self._timeout = timeout
        self._current_video_path: Optional[Path] = None
        
        logger.info(f"[VideoDownloader] 初始化: {self._save_dir}")

    def _generate_filename(self) -> str:
        """生成文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"video_{timestamp}.mp4"

    def _get_temp_path(self, final_path: Path) -> Path:
        """获取临时文件路径"""
        return final_path.with_suffix(final_path.suffix + self.TEMP_SUFFIX)

    def _get_video_files(self) -> List[Path]:
        """获取视频文件列表（按修改时间排序）"""
        files = []
        try:
            for f in self._save_dir.iterdir():
                if f.is_file() and f.suffix.lower() in ('.mp4', '.avi', '.mkv', '.mov', '.webm'):
                    files.append(f)
            files.sort(key=lambda x: x.stat().st_mtime)
        except Exception as e:
            logger.error(f"[VideoDownloader] 获取列表失败: {e}")
        return files

    def _cleanup_old_videos(self):
        """清理旧视频，保持文件数量在限制内"""
        try:
            files = self._get_video_files()
            
            while len(files) >= self.MAX_VIDEO_FILES:
                oldest = files.pop(0)
                try:
                    oldest.unlink()
                    logger.info(f"[VideoDownloader] 清理: {oldest.name}")
                except Exception as e:
                    logger.error(f"[VideoDownloader] 删除失败: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"[VideoDownloader] 清理失败: {e}")

    def _cleanup_temp_files(self):
        """清理过期的临时文件（超过1小时）"""
        try:
            now = datetime.now().timestamp()
            for f in self._save_dir.iterdir():
                if f.suffix == self.TEMP_SUFFIX:
                    age = now - f.stat().st_mtime
                    if age > 3600:  # 1小时
                        f.unlink()
                        logger.debug(f"[VideoDownloader] 清理临时文件: {f.name}")
        except Exception as e:
            logger.debug(f"[VideoDownloader] 清理临时文件失败: {e}")

    async def check_resume_support(self, url: str) -> bool:
        """
        检查 URL 是否支持断点续传
        
        Args:
            url: 视频 URL
            
        Returns:
            是否支持断点续传
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    accept_ranges = response.headers.get('Accept-Ranges', '')
                    return accept_ranges.lower() == 'bytes'
        except Exception:
            return False

    async def download(
        self,
        video_url: str,
        filename: Optional[str] = None,
        resume: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Tuple[bool, str]:
        """
        下载视频，支持断点续传
        
        Args:
            video_url: 视频 URL
            filename: 文件名（可选，自动生成）
            resume: 是否启用断点续传
            progress_callback: 进度回调函数 (downloaded_bytes, total_bytes)
            
        Returns:
            (成功, 文件路径或错误信息)
        """
        if not video_url:
            return False, "视频URL为空"

        # 清理旧文件
        self._cleanup_old_videos()
        self._cleanup_temp_files()

        # 确定文件路径
        if filename:
            final_path = self._save_dir / filename
        else:
            final_path = self._save_dir / self._generate_filename()
        
        temp_path = self._get_temp_path(final_path)
        self._current_video_path = final_path
        
        logger.info(f"[VideoDownloader] 开始下载: {final_path.name}")

        # 检查是否有未完成的下载
        downloaded_size = 0
        if resume and temp_path.exists():
            downloaded_size = temp_path.stat().st_size
            logger.info(f"[VideoDownloader] 发现未完成下载，已下载: {downloaded_size / 1024 / 1024:.2f} MB")

        try:
            headers = {}
            if downloaded_size > 0:
                headers['Range'] = f'bytes={downloaded_size}-'

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    video_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self._timeout)
                ) as response:
                    
                    # 处理响应状态
                    if downloaded_size > 0:
                        if response.status == 206:
                            # 服务器支持断点续传
                            mode = 'ab'
                            logger.info("[VideoDownloader] 断点续传模式")
                        elif response.status == 200:
                            # 服务器不支持，重新下载
                            downloaded_size = 0
                            mode = 'wb'
                            logger.warning("[VideoDownloader] 服务器不支持断点续传，重新下载")
                        else:
                            return False, f"HTTP {response.status}"
                    else:
                        if response.status != 200:
                            return False, f"HTTP {response.status}"
                        mode = 'wb'
                    
                    # 计算总大小
                    content_length = response.headers.get('Content-Length')
                    if content_length:
                        remaining_size = int(content_length)
                        total_size = remaining_size + downloaded_size
                    else:
                        total_size = 0
                    
                    # 下载
                    async with aiofiles.open(temp_path, mode) as f:
                        async for chunk in response.content.iter_chunked(self.CHUNK_SIZE):
                            await f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # 进度回调
                            if progress_callback and total_size > 0:
                                progress_callback(downloaded_size, total_size)

            # 下载完成，重命名临时文件
            if temp_path.exists():
                if final_path.exists():
                    final_path.unlink()
                temp_path.rename(final_path)
            
            if final_path.exists() and final_path.stat().st_size > 0:
                size_mb = final_path.stat().st_size / 1024 / 1024
                logger.info(f"[VideoDownloader] 下载完成: {size_mb:.2f} MB")
                return True, str(final_path)
            else:
                return False, "下载的文件为空"

        except aiohttp.ClientError as e:
            # 网络错误，保留临时文件以便续传
            logger.warning(f"[VideoDownloader] 网络错误: {e}，临时文件已保留")
            return False, f"网络错误: {e}"
            
        except asyncio.TimeoutError:
            logger.warning(f"[VideoDownloader] 下载超时，临时文件已保留")
            return False, f"下载超时 ({self._timeout}秒)"
            
        except Exception as e:
            logger.error(f"[VideoDownloader] 下载异常: {e}")
            return False, f"下载异常: {e}"

    def cleanup_current(self) -> bool:
        """清理当前视频文件"""
        try:
            if self._current_video_path:
                if self._current_video_path.exists():
                    self._current_video_path.unlink()
                
                # 同时清理临时文件
                temp_path = self._get_temp_path(self._current_video_path)
                if temp_path.exists():
                    temp_path.unlink()
                
                self._current_video_path = None
            return True
        except Exception as e:
            logger.error(f"[VideoDownloader] 清理失败: {e}")
            return False

    def get_download_progress(self, filename: str) -> Optional[Tuple[int, int]]:
        """
        获取下载进度
        
        Args:
            filename: 文件名
            
        Returns:
            (已下载大小, 总大小) 或 None
        """
        final_path = self._save_dir / filename
        temp_path = self._get_temp_path(final_path)
        
        if final_path.exists():
            size = final_path.stat().st_size
            return (size, size)  # 已完成
        elif temp_path.exists():
            size = temp_path.stat().st_size
            return (size, 0)  # 下载中，总大小未知
        
        return None