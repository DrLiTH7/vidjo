from __future__ import annotations
import os
import re
import shutil
import asyncio
import subprocess
import traceback
from log import logger
from typing import Tuple
from utils import get_url_basename, sanitize_filename
from urllib.parse import urljoin
from downloader import Downloader, Task
from config import DownloaderConfig, FfmpegConfig, GetConfig
from progress import files_progress, shared_progress
import aiofiles

class BlobDownloader:
    """Blob video downloader that supports both single and batch downloads"""

    def __init__(self, save_path: str = "", tmp_path: str = "", clean_tmp: bool = False):
        self.base_save_path = self._gen_video_path() if not save_path else save_path
        self.base_tmp_path = self._gen_tmp_path() if not tmp_path else tmp_path
        os.makedirs(self.base_save_path, exist_ok=True)
        self.clean_tmp = clean_tmp
        self.downloader = Downloader(**DownloaderConfig)

    def _gen_video_path(self) -> str:
        return os.path.join(os.path.expanduser("~"), "Downloads")

    def _gen_tmp_path(self) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_files")

    async def run(self, blob_url: str, save_name: str = "", headers: dict | None = None) -> str:
        """Download a single blob video."""
        async with self.downloader.session_context(headers=headers) as (session, sem):
            with shared_progress:
                return await self._download_single(blob_url, save_name, session, sem)

    async def run_batch(
        self,
        url_list: list,
        headers: dict | None = None,
        save_path: str | None = None,
        threads: int | None = None,
        max_concurrent: int | None = None,
        preferred_quality: str = "highest",
        progress_hook = None,
    ) -> list[str | Exception]:
        """Download multiple blob videos concurrently sharing one HTTP session."""
        items = self._parse_url_list(url_list)
        if not items:
            return []

        effective_save_path = save_path or self.base_save_path
        os.makedirs(effective_save_path, exist_ok=True)

        effective_threads = threads if threads is not None else FfmpegConfig.get("threads", 0)
        effective_max_concurrent = max_concurrent if max_concurrent is not None else DownloaderConfig.get("max_concurrent", 20)

        async with self.downloader.session_context(headers=headers, max_concurrent=effective_max_concurrent) as (session, sem):
            with shared_progress:
                coros = [
                    self._safe_download_single(url, name, session, sem, effective_save_path, effective_threads, preferred_quality, progress_hook)
                    for url, name in items
                ]
                return list(await asyncio.gather(*coros))

    def _parse_url_list(self, url_list: list) -> list[tuple]:
        items = []
        for item in url_list:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                url, save_name = item[0], item[1]
            elif isinstance(item, str):
                url, save_name = item, ""
            else:
                logger.error(f"Invalid item format: {item}")
                continue
            if save_name and not save_name.endswith(".mp4"):
                save_name = f"{save_name}.mp4"
            items.append((url, save_name))
        return items

    async def _safe_download_single(self, url: str, save_name: str, session, sem, save_dir: str | None = None, threads: int | None = None, preferred_quality: str = "highest", progress_hook = None) -> str | Exception:
        try:
            result = await self._download_single(url, save_name, session, sem, save_dir, threads, preferred_quality, progress_hook)
            logger.info(f"Successfully downloaded: {save_name or get_url_basename(url)}")
            return result
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}\n{traceback.format_exc()}")
            return e

    async def _download_single(self, blob_url: str, save_name: str, session, sem, save_dir: str | None = None, threads: int | None = None, preferred_quality: str = "highest", progress_hook = None) -> str:
        blob_url = blob_url.strip()
        if not save_name:
            import hashlib
            url_hash = hashlib.md5(blob_url.encode()).hexdigest()[:6]
            base = get_url_basename(blob_url)
            if base.endswith(".mp4"):
                save_name = f"{base[:-4]}_{url_hash}.mp4"
            else:
                save_name = f"{base}_{url_hash}.mp4"
        
        save_name = sanitize_filename(save_name)
        effective_save_dir = save_dir or self.base_save_path
        save_path = os.path.join(effective_save_dir, save_name)
        tmp_path = os.path.join(self.base_tmp_path, save_name)

        if os.path.exists(save_path):
            return save_path

        os.makedirs(tmp_path, exist_ok=True)
        
        basename = get_url_basename(blob_url).lower()
        if (".mp4" in basename or ".webm" in basename or ".mkv" in basename) and ".m3u8" not in basename:
            logger.info(f"Direct video download detected: {blob_url}")
            
            content_length = 0
            try:
                head_kwargs = dict(GetConfig)
                if not any(k.lower() == "referer" for k in head_kwargs.get("headers", {})):
                    from urllib.parse import urlparse
                    parsed = urlparse(blob_url)
                    head_kwargs.setdefault("headers", {})["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
                    
                async with session.head(blob_url, **head_kwargs) as head_resp:
                    if head_resp.status == 200:
                        cl = head_resp.headers.get("Content-Length")
                        if cl and cl.isdigit():
                            content_length = int(cl)
            except Exception as e:
                logger.warning(f"HEAD request failed: {e}")
                
            tasks = []
            num_chunks = 0
            if content_length > 0:
                logger.info(f"File size: {content_length} bytes. Splitting into chunks.")
                chunk_size = 5 * 1024 * 1024  # 5 MB chunks
                num_chunks = (content_length + chunk_size - 1) // chunk_size
                
                for i in range(num_chunks):
                    start = i * chunk_size
                    end = min(start + chunk_size - 1, content_length - 1)
                    part_path = os.path.join(tmp_path, f"part_{i:04d}")
                    if os.path.exists(part_path) and os.path.getsize(part_path) == (end - start + 1):
                        continue # already downloaded
                    task = Task(blob_url, part_path, headers={"Range": f"bytes={start}-{end}"})
                    tasks.append(task)
            
            if tasks:
                await self.async_load_media(tasks, session, sem, save_name, progress_hook)
            elif content_length == 0:
                # fallback to single connection
                task = Task(blob_url, save_path)
                await self.async_load_media([task], session, sem, save_name, progress_hook)
            
            if content_length > 0:
                logger.info(f"Merging {num_chunks} parts...")
                async with aiofiles.open(save_path, "wb") as out_f:
                    for i in range(num_chunks):
                        part_path = os.path.join(tmp_path, f"part_{i:04d}")
                        async with aiofiles.open(part_path, "rb") as in_f:
                            while True:
                                chunk = await in_f.read(4 * 1024 * 1024)
                                if not chunk:
                                    break
                                await out_f.write(chunk)
                        if progress_hook:
                            progress_hook({"step": "merging", "completed": i + 1, "total": num_chunks})
                            
            if self.clean_tmp:
                logger.info(f"clean up tmp_path: {tmp_path}")
                await asyncio.to_thread(shutil.rmtree, tmp_path)
            return save_path


        m3u8_file = await self.load_m3u8_file(blob_url, tmp_path, session, sem, save_name)
        # If the downloaded file is a master playlist, resolve to the preferred quality sub-stream
        v_m3u8_file, v_url, a_m3u8_file, a_url, s_m3u8_file, s_url = await self._resolve_master_playlist(
            m3u8_file, blob_url, tmp_path, session, sem, preferred_quality
        )
        
        local_v_m3u8, v_tasks = await asyncio.to_thread(
            self.parse_m3u8_file, v_m3u8_file, v_url, tmp_path, "local_video.m3u8"
        )
        all_tasks = v_tasks
        
        local_a_m3u8 = None
        if a_m3u8_file and a_url:
            local_a_m3u8, a_tasks = await asyncio.to_thread(
                self.parse_m3u8_file, a_m3u8_file, a_url, tmp_path, "local_audio.m3u8"
            )
            all_tasks.extend(a_tasks)

        local_s_m3u8 = None
        if s_m3u8_file and s_url:
            local_s_m3u8, s_tasks = await asyncio.to_thread(
                self.parse_m3u8_file, s_m3u8_file, s_url, tmp_path, "local_sub.m3u8"
            )
            all_tasks.extend(s_tasks)
            
        await self.async_load_media(all_tasks, session, sem, save_name, progress_hook)
        
        local_files = [local_v_m3u8]
        if local_a_m3u8:
            local_files.append(local_a_m3u8)
        if local_s_m3u8:
            local_files.append(local_s_m3u8)
            
        video_path = await self.merge_media(local_files, save_path, threads=threads, progress_hook=progress_hook)
        if self.clean_tmp:
            logger.info(f"clean up tmp_path: {tmp_path}")
            await asyncio.to_thread(shutil.rmtree, tmp_path)
        return video_path

    def _select_quality_stream(self, master_content: str, master_url: str, preferred_quality: str) -> tuple[str | None, str | None]:
        """Parse a master HLS playlist and return (video_url, audio_url)."""
        streams = []
        lines = master_content.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXT-X-STREAM-INF:"):
                bandwidth = 0
                quality_label = ""
                audio_group = None
                sub_group = None
                
                bw_match = re.search(r"BANDWIDTH=(\d+)", line)
                res_match = re.search(r"RESOLUTION=\d+x(\d+)", line)
                audio_match = re.search(r'AUDIO="([^"]+)"', line)
                sub_match = re.search(r'SUBTITLES="([^"]+)"', line)
                
                if bw_match:
                    bandwidth = int(bw_match.group(1))
                if res_match:
                    quality_label = f"{res_match.group(1)}p"
                if audio_match:
                    audio_group = audio_match.group(1)
                if sub_match:
                    sub_group = sub_match.group(1)
                    
                i += 1
                # Next non-empty, non-comment line is the stream URI
                while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith("#")):
                    i += 1
                if i < len(lines):
                    stream_uri = lines[i].strip()
                    stream_url = urljoin(master_url, stream_uri)
                    streams.append({"url": stream_url, "bandwidth": bandwidth, "quality": quality_label, "audio_group": audio_group, "sub_group": sub_group})
            i += 1

        if not streams:
            return None, None, None

        streams.sort(key=lambda s: s["bandwidth"])
        logger.info(f"Master playlist streams: {[s['quality'] or s['bandwidth'] for s in streams]}")

        if preferred_quality == "lowest":
            chosen = streams[0]
        elif preferred_quality == "highest":
            chosen = streams[-1]
        else:
            # Try exact label match (e.g. "1080p")
            chosen = next((s for s in streams if s["quality"] == preferred_quality), streams[-1])

        logger.info(f"Selected stream: quality={chosen['quality'] or 'unknown'}, bandwidth={chosen['bandwidth']}, url={chosen['url']}")
        
        audio_url = None
        if chosen.get("audio_group"):
            for line in lines:
                if line.startswith("#EXT-X-MEDIA:TYPE=AUDIO") and f'GROUP-ID="{chosen["audio_group"]}"' in line:
                    uri_match = re.search(r'URI="([^"]+)"', line)
                    if uri_match:
                        audio_url = urljoin(master_url, uri_match.group(1))
                        logger.info(f"Found separated audio stream for group {chosen['audio_group']}: {audio_url}")
                        break

        sub_url = None
        if chosen.get("sub_group"):
            for line in lines:
                if line.startswith("#EXT-X-MEDIA:TYPE=SUBTITLES") and f'GROUP-ID="{chosen["sub_group"]}"' in line:
                    uri_match = re.search(r'URI="([^"]+)"', line)
                    if uri_match:
                        sub_url = urljoin(master_url, uri_match.group(1))
                        logger.info(f"Found separated subtitle stream for group {chosen['sub_group']}: {sub_url}")
                        break

        return chosen["url"], audio_url, sub_url

    async def _resolve_master_playlist(
        self, m3u8_file: str, m3u8_url: str, tmp_path: str, session, sem, preferred_quality: str
    ) -> tuple[str, str, str | None, str | None, str | None, str | None]:
        """If the m3u8 is a master playlist, download and return the chosen sub-stream m3u8, audio m3u8 and sub m3u8."""
        with open(m3u8_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if "#EXT-X-STREAM-INF" not in content:
            return m3u8_file, m3u8_url, None, None, None, None

        logger.info("Master playlist detected — selecting quality stream...")
        stream_url, audio_url, sub_url = self._select_quality_stream(content, m3u8_url, preferred_quality)
        if not stream_url:
            logger.warning("Could not parse streams from master playlist; using as-is.")
            return m3u8_file, m3u8_url, None, None, None, None

        stream_m3u8_file = os.path.join(tmp_path, get_url_basename(stream_url))
        tasks_to_fetch = [Task(stream_url, stream_m3u8_file)]
        
        audio_m3u8_file = None
        if audio_url:
            audio_m3u8_file = os.path.join(tmp_path, "audio_" + get_url_basename(audio_url))
            tasks_to_fetch.append(Task(audio_url, audio_m3u8_file))
            
        sub_m3u8_file = None
        if sub_url:
            sub_m3u8_file = os.path.join(tmp_path, "sub_" + get_url_basename(sub_url))
            tasks_to_fetch.append(Task(sub_url, sub_m3u8_file))
            
        result = await self.downloader.fetch_all(session, sem, tasks_to_fetch, desc="stream m3u8(s)")
        if not result or any(r is False for r in result):
            raise Exception(f"Failed to download stream m3u8s from master playlist")

        return stream_m3u8_file, stream_url, audio_m3u8_file, audio_url, sub_m3u8_file, sub_url

    async def load_m3u8_file(
        self, blob_url: str, tmp_path: str, session, sem, label: str = ""
    ) -> str:
        m3u8_file = os.path.join(tmp_path, get_url_basename(blob_url))
        if os.path.exists(m3u8_file):
            return m3u8_file
        task = Task(blob_url, m3u8_file)
        desc = f"[{label}] m3u8" if label else "downloading m3u8"
        result = await self.downloader.fetch_all(session, sem, [task], desc=desc)
        if len(result) == 0 or result[0] is False:
            raise Exception("failed to download m3u8 file")
        return m3u8_file

    def parse_m3u8_file(
        self, m3u8_file: str, blob_url: str, tmp_path: str, local_name: str = "local.m3u8"
    ) -> Tuple[str, list[Task]]:
        local_m3u8_file = os.path.join(tmp_path, local_name)
        tasks = []
        total_count = 0
        already_downloaded = 0
        with open(m3u8_file, "r", encoding="utf-8") as raw_m3u8, open(local_m3u8_file, "w", encoding="utf-8") as local_m3u8:
            for line in raw_m3u8:
                if line.startswith("#"):
                    ts_url, line = self.parse_meta_data(line, blob_url, tmp_path)
                else:
                    ts_url, line = self.parse_media_segment(line, blob_url, tmp_path)
                local_m3u8.write(line)
                if not ts_url:
                    continue
                total_count += 1
                
                file_name = get_url_basename(ts_url)
                if file_name.endswith(".webvtt"):
                    file_name = file_name[:-7] + ".vtt"
                    
                save_path = os.path.join(tmp_path, file_name)
                if os.path.exists(save_path):
                    already_downloaded += 1
                    continue
                tasks.append(Task(ts_url, save_path))
        if already_downloaded > 0:
            logger.info(
                f"resuming: {already_downloaded}/{total_count} segments already on disk, "
                f"downloading remaining {len(tasks)}"
            )
        else:
            logger.info(f"total: {total_count}, need to download: {len(tasks)}")
        return local_m3u8_file, tasks

    async def async_load_media(
        self, tasks: list[Task], session, sem, label: str = "", progress_hook = None
    ):
        desc = f"[{label}] segments" if label else "downloading segments"
        results = await self.downloader.fetch_all(session, sem, tasks, desc=desc, progress_hook=progress_hook)
        failed_count = len([r for r in results if not r])
        if failed_count > 0:
            raise Exception(
                f"total task: {len(tasks)}, failed task: {failed_count}\n"
                "Please check error and retry again, some media are still not downloaded yet."
            )
        logger.info("download media success!")

    async def merge_media(self, local_m3u8_files: list[str], save_path: str, threads: int | None = None, progress_hook = None) -> str:
        threads = threads if threads is not None else FfmpegConfig.get("threads", 0)

        ffmpeg_cmd = [
            "ffmpeg",
            "-fflags", "+genpts",
            "-allowed_extensions", "ALL",
            "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
        ]
        
        for local_file in local_m3u8_files:
            ffmpeg_cmd.extend(["-i", local_file])
            
        # Ensure compatibility with mp4 subtitle formats if subtitles are present
        if len(local_m3u8_files) > 2:
            ffmpeg_cmd.extend(["-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text"])
        else:
            ffmpeg_cmd.extend(["-c", "copy"])
            
        if threads > 0:
            ffmpeg_cmd += ["-threads", str(threads)]
        ffmpeg_cmd += [save_path, "-y"]

        logger.info(f"ffmpeg is merging... (threads={'auto' if threads == 0 else threads})")

        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW

        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            creationflags=creationflags
        )

        merge_task = files_progress.add_task(description="merging", total=100)
        duration_secs: float | None = None
        stderr_output: list[str] = []

        assert proc.stderr is not None
        async for raw_line in proc.stderr:
            line = raw_line.decode(errors="replace")
            stderr_output.append(line)

            # Detect total duration once (printed near the start by ffmpeg)
            if duration_secs is None:
                m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", line)
                if m:
                    h, mn, s, cs = (int(m.group(i)) for i in range(1, 5))
                    duration_secs = h * 3600 + mn * 60 + s + cs / 100

            # Update progress bar with current timestamp
            m = re.search(r"time=(\d+):(\d+):(\d+)\.(\d+)", line)
            if m and duration_secs:
                h, mn, s, cs = (int(m.group(i)) for i in range(1, 5))
                current = h * 3600 + mn * 60 + s + cs / 100
                pct = min(100, int(current / duration_secs * 100))
                files_progress.update(merge_task, completed=pct)
                if progress_hook:
                    progress_hook({"step": "merging", "completed": pct, "total": 100})

        try:
            await proc.wait()
        except asyncio.CancelledError:
            try:
                proc.kill()
            except OSError:
                pass
            raise
        finally:
            files_progress.update(merge_task, completed=100)
            files_progress.remove_task(merge_task)

        if proc.returncode != 0:
            raise Exception(f"ffmpeg failed:\n{''.join(stderr_output)}")

        logger.info(f"finished download blob video! {save_path}")
        return save_path

    def parse_meta_data(self, line: str, blob_url: str, tmp_path: str) -> Tuple[str, str]:
        search_res = re.search(r'URI="(.+?)"', line)
        if not search_res:
            return "", line
        key_ts = search_res.group(1)
        key_url = urljoin(blob_url, key_ts)
        clean_key_ts_name = get_url_basename(key_ts)
        key_line = line.replace(key_ts, f"{tmp_path}/{clean_key_ts_name}").replace("\\", "/")
        return key_url, key_line

    def parse_media_segment(self, line: str, blob_url: str, tmp_path: str) -> Tuple[str, str]:
        ts_line = line.rstrip()
        if not ts_line:
            return "", line
        ts_url = urljoin(blob_url, ts_line)
        file_name = get_url_basename(ts_url)
        if file_name.endswith(".webvtt"):
            file_name = file_name[:-7] + ".vtt"
        local_line = os.path.join(tmp_path, file_name).replace("\\", "/") + "\n"
        return ts_url, local_line
