import asyncio
from config import DownloaderConfig
from downloader import Downloader, Task


def test_downloader_init():
    downloader = Downloader(**DownloaderConfig)
    assert downloader.max_concurrent == DownloaderConfig["max_concurrent"]
    assert downloader.max_retry == DownloaderConfig["max_retry"]


def test_fetch_all_empty_tasks():
    """fetch_all with no tasks returns [] without making any network requests."""
    async def _run():
        downloader = Downloader(**DownloaderConfig)
        async with downloader.session_context() as (session, sem):
            return await downloader.fetch_all(session, sem, [], "test")

    assert asyncio.run(_run()) == []
