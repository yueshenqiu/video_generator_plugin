"""视频下载模块 - 支持断点续传"""

import asyncio
import logging
import aiohttp
import aiofiles
from datetime import datetime
from typing import Optional, Tuple, List, Callable
from pathlib import Path


class VideoDownloader:
    """视频下载器 - 支持断点续传"""

    MAX_VIDEO_FILES = 10
    CHUNK_SIZE = 8192
    TEMP_SUFFIX = ".tmp"

    def __init__(
        self,
        save_dir: Optional[str] = None,
        timeout: int = 300,
        logger: Optional[logging.Logger] = None,
    ):
        self._logger = logger or logging.getLogger("video_generator.downloader")
        
        if save_dir:
            self._save_dir = Path(save_dir)
        else:
            self._save_dir = Path(__file__).parent.parent / "temp"
        
        self._save_dir.mkdir(parents=True, exist_ok=True)
        self._timeout = timeout
        self._current_video_path: Optional[Path] = None
        
        self._logger.debug(f"[VideoDownloader] 初始化: {self._save_dir}")

    def _generate_filename(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"video_{timestamp}.mp4"

    def _get_temp_path(self, final_path: Path) -> Path:
        return final_path.with_suffix(final_path.suffix + self.TEMP_SUFFIX)

    def _get_video_files(self) -> List[Path]:
        files = []
        try:
            for f in self._save_dir.iterdir():
                if f.is_file() and f.suffix.lower() in ('.mp4', '.avi', '.mkv', '.mov', '.webm'):
                    files.append(f)
            files.sort(key=lambda x: x.stat().st_mtime)
        except Exception as e:
            self._logger.error(f"[VideoDownloader] 获取列表失败: {e}")
        return files

    def _cleanup_old_videos(self):
        try:
            files = self._get_video_files()
            while len(files) >= self.MAX_VIDEO_FILES:
                oldest = files.pop(0)
                try:
                    oldest.unlink()
                    self._logger.info(f"[VideoDownloader] 清理: {oldest.name}")
                except Exception as e:
                    self._logger.error(f"[VideoDownloader] 删除失败: {e}")
                    break
        except Exception as e:
            self._logger.error(f"[VideoDownloader] 清理失败: {e}")

    def _cleanup_temp_files(self):
        try:
            now = datetime.now().timestamp()
            for f in self._save_dir.iterdir():
                if f.suffix == self.TEMP_SUFFIX:
                    age = now - f.stat().st_mtime
                    if age > 3600:
                        f.unlink()
                        self._logger.debug(f"[VideoDownloader] 清理临时文件: {f.name}")
        except Exception as e:
            self._logger.debug(f"[VideoDownloader] 清理临时文件失败: {e}")

    async def check_resume_support(self, url: str) -> bool:
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
        if not video_url:
            return False, "视频URL为空"

        self._cleanup_old_videos()
        self._cleanup_temp_files()

        if filename:
            final_path = self._save_dir / filename
        else:
            final_path = self._save_dir / self._generate_filename()
        
        temp_path = self._get_temp_path(final_path)
        self._current_video_path = final_path
        
        self._logger.info(f"[VideoDownloader] 开始下载: {final_path.name}")

        downloaded_size = 0
        if resume and temp_path.exists():
            downloaded_size = temp_path.stat().st_size
            self._logger.info(f"[VideoDownloader] 发现未完成下载，已下载: {downloaded_size / 1024 / 1024:.2f} MB")

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
                    
                    if downloaded_size > 0:
                        if response.status == 206:
                            mode = 'ab'
                            self._logger.info("[VideoDownloader] 断点续传模式")
                        elif response.status == 200:
                            downloaded_size = 0
                            mode = 'wb'
                            self._logger.warning("[VideoDownloader] 服务器不支持断点续传，重新下载")
                        else:
                            return False, f"HTTP {response.status}"
                    else:
                        if response.status != 200:
                            return False, f"HTTP {response.status}"
                        mode = 'wb'
                    
                    content_length = response.headers.get('Content-Length')
                    if content_length:
                        remaining_size = int(content_length)
                        total_size = remaining_size + downloaded_size
                    else:
                        total_size = 0
                    
                    async with aiofiles.open(temp_path, mode) as f:
                        async for chunk in response.content.iter_chunked(self.CHUNK_SIZE):
                            await f.write(chunk)
                            downloaded_size += len(chunk)
                            if progress_callback and total_size > 0:
                                progress_callback(downloaded_size, total_size)

            if temp_path.exists():
                if final_path.exists():
                    final_path.unlink()
                temp_path.rename(final_path)
            
            if final_path.exists() and final_path.stat().st_size > 0:
                size_mb = final_path.stat().st_size / 1024 / 1024
                self._logger.info(f"[VideoDownloader] 下载完成: {size_mb:.2f} MB")
                return True, str(final_path)
            else:
                return False, "下载的文件为空"

        except aiohttp.ClientError as e:
            self._logger.warning(f"[VideoDownloader] 网络错误: {e}，临时文件已保留")
            return False, f"网络错误: {e}"
            
        except asyncio.TimeoutError:
            self._logger.warning("[VideoDownloader] 下载超时，临时文件已保留")
            return False, f"下载超时 ({self._timeout}秒)"
            
        except Exception as e:
            self._logger.error(f"[VideoDownloader] 下载异常: {e}")
            return False, f"下载异常: {e}"

    def cleanup_current(self) -> bool:
        try:
            if self._current_video_path:
                if self._current_video_path.exists():
                    self._current_video_path.unlink()
                temp_path = self._get_temp_path(self._current_video_path)
                if temp_path.exists():
                    temp_path.unlink()
                self._current_video_path = None
            return True
        except Exception as e:
            self._logger.error(f"[VideoDownloader] 清理失败: {e}")
            return False

    def get_download_progress(self, filename: str) -> Optional[Tuple[int, int]]:
        final_path = self._save_dir / filename
        temp_path = self._get_temp_path(final_path)
        
        if final_path.exists():
            size = final_path.stat().st_size
            return (size, size)
        elif temp_path.exists():
            size = temp_path.stat().st_size
            return (size, 0)
        
        return None