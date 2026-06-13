"""统一的异步 HTTP 客户端"""

import asyncio
import logging
import aiohttp
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    retry_on_status: tuple = (429, 500, 502, 503, 504)


class AsyncHttpClient:
    """统一的异步 HTTP 客户端"""
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 300,
        retry_config: Optional[RetryConfig] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.retry_config = retry_config or RetryConfig()
        self._logger = logger or logging.getLogger("video_generator.http")
    
    def _get_headers(self, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers
    
    def _calculate_delay(self, attempt: int) -> float:
        delay = self.retry_config.base_delay * (2 ** attempt)
        return min(delay, self.retry_config.max_delay)
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(extra_headers)
        last_error = None
        
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    kwargs = {
                        "headers": headers,
                        "timeout": aiohttp.ClientTimeout(total=self.timeout),
                    }
                    
                    if data is not None:
                        kwargs["json"] = data
                    if params is not None:
                        kwargs["params"] = params
                    
                    async with session.request(method, url, **kwargs) as response:
                        if response.status in self.retry_config.retry_on_status:
                            if attempt < self.retry_config.max_retries:
                                delay = self._calculate_delay(attempt)
                                self._logger.warning(
                                    f"[HTTP] {method} {endpoint} 返回 {response.status}，"
                                    f"{delay:.1f}秒后重试 ({attempt + 1}/{self.retry_config.max_retries})"
                                )
                                await asyncio.sleep(delay)
                                continue
                        
                        try:
                            result = await response.json()
                        except aiohttp.ContentTypeError:
                            text = await response.text()
                            result = {"raw_response": text}
                        
                        if response.status >= 400:
                            error_msg = self._extract_error_message(result, response.status)
                            raise HttpError(response.status, error_msg, result)
                        
                        return result
                        
            except aiohttp.ClientError as e:
                last_error = e
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_delay(attempt)
                    self._logger.warning(
                        f"[HTTP] {method} {endpoint} 网络错误: {e}，"
                        f"{delay:.1f}秒后重试 ({attempt + 1}/{self.retry_config.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                    
            except asyncio.TimeoutError:
                last_error = TimeoutError(f"请求超时 ({self.timeout}秒)")
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_delay(attempt)
                    self._logger.warning(
                        f"[HTTP] {method} {endpoint} 超时，"
                        f"{delay:.1f}秒后重试 ({attempt + 1}/{self.retry_config.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
        
        if last_error:
            raise last_error
        raise Exception("请求失败，未知错误")
    
    def _extract_error_message(self, result: Dict, status_code: int) -> str:
        if "error" in result:
            error = result["error"]
            if isinstance(error, dict):
                return error.get("message", str(error))
            return str(error)
        if "message" in result:
            return result["message"]
        if "msg" in result:
            return result["msg"]
        return f"HTTP {status_code}"
    
    async def post(self, endpoint: str, data: Dict, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return await self._request("POST", endpoint, data=data, extra_headers=extra_headers)
    
    async def get(self, endpoint: str, params: Optional[Dict] = None, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return await self._request("GET", endpoint, params=params, extra_headers=extra_headers)
    
    async def delete(self, endpoint: str, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return await self._request("DELETE", endpoint, extra_headers=extra_headers)


class HttpError(Exception):
    """HTTP 错误"""
    
    def __init__(self, status_code: int, message: str, response: Optional[Dict] = None):
        self.status_code = status_code
        self.message = message
        self.response = response
        super().__init__(f"HTTP {status_code}: {message}")