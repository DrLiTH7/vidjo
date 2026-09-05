from __future__ import annotations
import aiohttp
import asyncio
import aiofiles
import contextlib
import traceback
from log import logger
from rich.progress import TaskID
from progress import files_progress
from config import GetConfig, ConnectorConfig, HeaderConfig


class Task:
    """Task represents a download task with URL and save path"""
    url: str
    save_path: str
    headers: dict | None

    def __init__(self, url: str, save_path: str, headers: dict | None = None) -> None:
        self.url = url
        self.save_path = save_path
        self.headers = headers


class DownloadError(Exception):
    """Custom exception for download failures"""

    def __init__(self, url: str, message: str, retry_count: int = 0):
        self.url = url
        self.message = message
        self.retry_count = retry_count
        super().__init__(f"Download failed for {url}: {message} (retries: {retry_count})")


class Downloader:
    def __init__(self, max_concurrent: int = 20, max_retry: int = 3):
        self.max_concurrent = max_concurrent
        self.max_retry = max_retry
        self.connector = None

    @contextlib.asynccontextmanager
    async def session_context(self, headers: dict | None = None, max_concurrent: int | None = None):
        """Open a single aiohttp session and semaphore to be shared across all downloads."""
        sem = asyncio.Semaphore(max_concurrent if max_concurrent is not None else self.max_concurrent)
        
        if self.connector is None or self.connector.closed:
            connector_args = dict(ConnectorConfig)
            connector_args["force_close"] = True  # Prevent HTTP 421 CDN connection reuse issues
            self.connector = aiohttp.TCPConnector(**connector_args)
            
        session_headers = dict(headers) if headers else dict(HeaderConfig)
        
        # Ensure a default User-Agent is present if headers were empty or missing it
        has_ua = any(k.lower() == "user-agent" for k in session_headers.keys())
        if not has_ua:
            session_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
        # Clean up dummy exemple.com headers
        for k in list(session_headers.keys()):
            if "exemple.com" in str(session_headers[k]).lower():
                del session_headers[k]
        
        timeout = aiohttp.ClientTimeout(total=0, connect=60, sock_read=60)
        async with aiohttp.ClientSession(headers=session_headers, connector=self.connector, connector_owner=False, timeout=timeout) as session:
            yield session, sem

    async def fetch_all(
        self,
        session: aiohttp.ClientSession,
        sem: asyncio.Semaphore,
        tasks: list[Task],
        desc: str = "downloading",
        progress_hook = None,
    ) -> list[bool]:
        if not tasks:
            return []
        task_id = files_progress.add_task(description=desc, total=len(tasks))
        if progress_hook:
            progress_hook({"step": "downloading", "completed": 0, "total": len(tasks)})
        coros = [
            self._safe_fetch_url(session, task_id, t, sem, progress_hook)
            for t in tasks
        ]
        return list(await asyncio.gather(*coros))

    async def _safe_fetch_url(
        self,
        session: aiohttp.ClientSession,
        task_id: TaskID,
        task: Task,
        sem: asyncio.Semaphore,
        progress_hook = None,
    ) -> bool:
        try:
            return await self.fetch_url(session, task_id, task, sem, progress_hook)
        except DownloadError as e:
            logger.error(f"Download failed: {e}")
            return False

    async def fetch_url(
        self,
        session: aiohttp.ClientSession,
        task_id: TaskID,
        task: Task,
        sem: asyncio.Semaphore,
        progress_hook = None,
    ) -> bool:
        for retry in range(self.max_retry + 1):
            try:
                async with sem:
                    kwargs = dict(GetConfig)
                    if task.headers:
                        kwargs["headers"] = kwargs.get("headers", {}) | task.headers
                    
                    # Auto-inject Referer to bypass hotlink protection if not present
                    if not any(k.lower() == "referer" for k in session.headers) and not any(k.lower() == "referer" for k in kwargs.get("headers", {})):
                        from urllib.parse import urlparse
                        parsed = urlparse(task.url)
                        kwargs.setdefault("headers", {})["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
                        
                    async with session.get(task.url, **kwargs) as response:
                        if response.status not in (200, 206):
                            if response.status >= 500 or response.status == 421 or response.status == 429:
                                raise aiohttp.ClientError(f"HTTP_{response.status}")
                            raise DownloadError(task.url, f"HTTP_{response.status}", retry)
                        await self.save_as_file(response, task.save_path)
                        files_progress.advance(task_id, advance=1)
                        if progress_hook:
                            task_info = [t for t in files_progress.tasks if t.id == task_id]
                            if task_info:
                                progress_hook({"step": "downloading", "completed": task_info[0].completed, "total": task_info[0].total})
                        return True
            except DownloadError:
                raise
            except (asyncio.TimeoutError, aiohttp.ClientError, OSError) as e:
                if retry < self.max_retry:
                    logger.error(f"FAILED: [{task.url}][retry: {retry+1}][error: {type(e).__name__}({str(e)})]")
                    await asyncio.sleep(0.5)
                    continue
                error_msg = f"Connection error after {retry} retries: {type(e).__name__}({str(e)})"
                logger.error(f"FAILED: [{task.url}][retry_done: {retry}][error: {error_msg}]")
                raise DownloadError(task.url, error_msg, retry)
            except Exception:
                logger.error(f"FAILED: [{task.url}][error: {traceback.format_exc()}]")
                raise DownloadError(task.url, f"Unexpected error", retry)

    async def save_as_file(self, response: aiohttp.ClientResponse, save_path: str):
        async with aiofiles.open(save_path, "wb") as fp:
            async for chunk in response.content.iter_chunked(262144):
                await fp.write(chunk)
