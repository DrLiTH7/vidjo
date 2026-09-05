import json
import shutil
import asyncio
import traceback
import uuid
import os
import time
import re
import subprocess
from aiohttp import web
from core import BlobDownloader
from log import logger

# Store the global downloader instance
downloader = BlobDownloader(clean_tmp=True)

# Global dict to store task progress
active_tasks = {}

# Dict to store the actual asyncio.Task objects for cancellation
running_tasks = {}

TASKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.json")

# Set of asyncio Queues for active SSE connections
sse_queues = set()

def broadcast_update(task_id):
    if task_id in active_tasks:
        payload = {"task_id": task_id, "data": active_tasks[task_id]}
        for q in sse_queues:
            # We use put_nowait so we don't block
            q.put_nowait(payload)


async def handle_download(request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON payload"}, status=400)

    url = data.get("url")
    headers = data.get("headers", {})
    # Remove headers that cause issues with connection pooling, SNI routing, or CDN wafs
    for h in ["host", "connection", "accept-encoding"]:
        headers.pop(h, None)
        
    save_path = (data.get("save_path") or "").strip().strip('"').strip("'").strip() or None
    threads = data.get("threads", None)
    max_concurrent = data.get("max_concurrent", None)
    preferred_quality = data.get("preferred_quality", "highest")
    title = data.get("title", "")
    engine = data.get("engine", "native")

    if not url:
        return web.json_response({"error": "Missing 'url' parameter"}, status=400)

    logger.info(f"Received download request from extension for: {url}")
    if save_path:
        logger.info(f"  save_path override: {save_path}")
    if threads is not None:
        logger.info(f"  ffmpeg threads override: {threads}")
    if max_concurrent is not None:
        logger.info(f"  max_concurrent override: {max_concurrent}")
    logger.info(f"  preferred_quality: {preferred_quality}")

    task_id = str(uuid.uuid4())
    
    if title:
        clean_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
        clean_title = clean_title[:80]
        save_name = f"{clean_title}_{task_id[:4]}.mp4"
    else:
        save_name = f"video_{int(time.time())}_{task_id[:8]}.mp4"

    active_tasks[task_id] = {
        "status": "starting", 
        "url": url, 
        "title": title,
        "headers": headers,
        "save_path": save_path,
        "threads": threads,
        "max_concurrent": max_concurrent,
        "preferred_quality": preferred_quality,
        "save_name": save_name,
        "engine": engine
    }
    broadcast_update(task_id)

    if engine == "ytdlp":
        task = asyncio.create_task(run_ytdlp_download(task_id, url, save_path, save_name))
    else:
        task = asyncio.create_task(run_download_task(task_id, url, headers, save_path, threads, max_concurrent, preferred_quality, save_name))
    
    running_tasks[task_id] = task

    return web.json_response({"status": "Download started", "task_id": task_id, "url": url})

async def handle_status(request):
    task_id = request.query.get("task_id")
    if task_id:
        if task_id in active_tasks:
            return web.json_response({"task_id": task_id, "data": active_tasks[task_id]})
        return web.json_response({"error": "Task not found"}, status=404)
    return web.json_response({"tasks": active_tasks})

async def run_download_task(task_id, url, headers, save_path, threads, max_concurrent, preferred_quality, save_name):
    try:
        def progress_hook(info):
            if task_id in active_tasks:
                active_tasks[task_id].update(info)
                broadcast_update(task_id)

        clean_headers = None
        if headers:
            clean_headers = {}
            for k, v in headers.items():
                clean_headers[k.lower()] = str(v)

        results = await downloader.run_batch(
            [(url, save_name)],
            headers=clean_headers,
            save_path=save_path,
            threads=threads,
            max_concurrent=max_concurrent,
            preferred_quality=preferred_quality,
            progress_hook=progress_hook,
        )
        successful = [r for r in results if not isinstance(r, Exception) and r is not None]
        failed = [r for r in results if isinstance(r, Exception)]
        if successful:
            logger.info("Successfully downloaded video from extension request!")
            active_tasks[task_id]["status"] = "done"
        else:
            error_msg = str(failed[0]) if failed else "Unknown download error"
            logger.error(f"Download failed: {error_msg}")
            
            # Auto fallback to yt-dlp if available
            has_ytdlp = shutil.which("yt-dlp") is not None or os.path.exists(os.path.join("venv", "Scripts", "yt-dlp.exe"))
            if has_ytdlp and not active_tasks[task_id].get("_fallback_attempted"):
                logger.info(f"Task {task_id} failed natively, auto-falling back to yt-dlp...")
                active_tasks[task_id]["_fallback_attempted"] = True
                active_tasks[task_id]["engine"] = "ytdlp"
                broadcast_update(task_id)
                # Call yt-dlp download instead
                await run_ytdlp_download(task_id, url, save_path, save_name, headers)
                return
                
            active_tasks[task_id]["status"] = "error"
            active_tasks[task_id]["error"] = f"Falha no Download: {error_msg}"
        broadcast_update(task_id)
    except asyncio.CancelledError:
        logger.info(f"Task {task_id} was cancelled by user")
        if task_id in active_tasks:
            active_tasks[task_id]["status"] = "error"
            active_tasks[task_id]["error"] = "Cancelado pelo usuário"
            broadcast_update(task_id)
        raise
    except Exception as e:
        logger.error(f"Error executing download from extension: {e}\n{traceback.format_exc()}")
        if task_id in active_tasks:
            has_ytdlp = shutil.which("yt-dlp") is not None or os.path.exists(os.path.join("venv", "Scripts", "yt-dlp.exe"))
            if has_ytdlp and not active_tasks[task_id].get("_fallback_attempted"):
                logger.info(f"Task {task_id} threw an exception natively, auto-falling back to yt-dlp...")
                active_tasks[task_id]["_fallback_attempted"] = True
                active_tasks[task_id]["engine"] = "ytdlp"
                broadcast_update(task_id)
                await run_ytdlp_download(task_id, url, save_path, save_name, headers)
                return
                
            active_tasks[task_id]["status"] = "error"
            active_tasks[task_id]["error"] = str(e)
            broadcast_update(task_id)
    finally:
        running_tasks.pop(task_id, None)

async def run_ytdlp_download(task_id, url, save_path, save_name, headers=None):
    try:
        def progress_hook(info):
            if task_id in active_tasks:
                active_tasks[task_id].update(info)
                broadcast_update(task_id)
        
        final_save_path = save_path if save_path else os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.exists(final_save_path):
            os.makedirs(final_save_path)
            
        final_file = os.path.join(final_save_path, save_name)
        
        args = [
            "yt-dlp",
            "--newline",
            "--no-playlist",
            "-f", "bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
            "-o", final_file
        ]
        
        if headers:
            for k, v in headers.items():
                if k.lower() == "referer":
                    args.extend(["--referer", v])
                elif k.lower() == "user-agent":
                    args.extend(["--user-agent", v])
                else:
                    args.extend(["--add-header", f"{k}:{v}"])
                    
        args.append(url)
        
        logger.info(f"Starting yt-dlp fallback download for {url}")
        
        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            creationflags=creationflags
        )
        
        error_lines = []
        assert proc.stdout is not None
        async for raw_line in proc.stdout:
            line = raw_line.decode(errors="replace").strip()
            
            if "ERROR:" in line or "Exception:" in line:
                error_lines.append(line)
            
            m = re.search(r"\[download\]\s+([\d\.]+)%", line)
            if m:
                pct = float(m.group(1))
                progress_hook({"step": "downloading", "completed": int(pct), "total": 100})
            
            if "[Merger]" in line:
                progress_hook({"step": "merging", "completed": 0, "total": 100})
                
        try:
            await proc.wait()
        except asyncio.CancelledError:
            try:
                proc.kill()
            except OSError:
                pass
            raise

        if proc.returncode != 0:
            err_msg = " ".join(error_lines) if error_lines else f"exited with code {proc.returncode}"
            raise Exception(f"yt-dlp error: {err_msg}")

        logger.info("Successfully downloaded video using yt-dlp!")
        active_tasks[task_id]["status"] = "done"
        broadcast_update(task_id)
    except asyncio.CancelledError:
        logger.info(f"Task {task_id} (yt-dlp) was cancelled by user")
        if task_id in active_tasks:
            active_tasks[task_id]["status"] = "error"
            active_tasks[task_id]["error"] = "Cancelado pelo usuário"
            broadcast_update(task_id)
        raise
    except Exception as e:
        logger.error(f"Error executing yt-dlp download: {e}\n{traceback.format_exc()}")
        if task_id in active_tasks:
            active_tasks[task_id]["status"] = "error"
            active_tasks[task_id]["error"] = str(e)
            broadcast_update(task_id)
    finally:
        running_tasks.pop(task_id, None)

async def load_and_resume_tasks(app):
    global active_tasks
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                saved_tasks = json.load(f)
                active_tasks.update(saved_tasks)
            
            for task_id, data in active_tasks.items():
                if data.get("status") not in ("done", "error"):
                    logger.info(f"Auto-resuming task {task_id}")
                    engine = data.get("engine", "native")
                    if engine == "ytdlp":
                        task = asyncio.create_task(run_ytdlp_download(
                            task_id,
                            data.get("url"),
                            data.get("save_path"),
                            data.get("save_name"),
                            data.get("headers")
                        ))
                    else:
                        task = asyncio.create_task(run_download_task(
                            task_id,
                            data.get("url"),
                            data.get("headers"),
                            data.get("save_path"),
                            data.get("threads"),
                            data.get("max_concurrent"),
                            data.get("preferred_quality", "highest"),
                            data.get("save_name")
                        ))
                    running_tasks[task_id] = task
        except Exception as e:
            logger.error(f"Error loading tasks from JSON: {e}")

async def save_tasks_loop(app):
    try:
        while True:
            await asyncio.sleep(3)
            try:
                with open(TASKS_FILE, "w", encoding="utf-8") as f:
                    json.dump(active_tasks, f)
            except Exception as e:
                logger.error(f"Error saving tasks: {e}")
    except asyncio.CancelledError:
        pass

def create_app():
    app = web.Application()
    
    app.on_startup.append(load_and_resume_tasks)
    
    async def start_background_tasks(app):
        app['save_tasks_task'] = asyncio.create_task(save_tasks_loop(app))
    
    async def cleanup_background_tasks(app):
        app['save_tasks_task'].cancel()
        await app['save_tasks_task']
        
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    # Add CORS support to allow the extension to send requests
    async def add_cors_headers(request, response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    app.on_response_prepare.append(add_cors_headers)
    
    async def handle_options(request):
        return web.Response(status=200)

    async def handle_stream(request):
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
            }
        )
        await response.prepare(request)

        # Send initial state
        try:
            initial_data = json.dumps({"tasks": active_tasks})
            await response.write(f"data: {initial_data}\n\n".encode('utf-8'))
        except Exception as e:
            logger.error(f"Error sending initial state: {e}")
            return response

        queue = asyncio.Queue()
        sse_queues.add(queue)

        try:
            while True:
                # Wait for updates to the queue
                update = await queue.get()
                update_data = json.dumps(update)
                await response.write(f"data: {update_data}\n\n".encode('utf-8'))
        except asyncio.CancelledError:
            pass
        finally:
            sse_queues.discard(queue)

        return response

    async def handle_cancel(request):
        try:
            data = await request.json()
            task_id = data.get("task_id")
            if task_id and task_id in running_tasks:
                running_tasks[task_id].cancel()
                return web.json_response({"status": "cancelled"})
            return web.json_response({"error": "Task not found or not running"}, status=404)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_open_folder(request):
        try:
            data = await request.json()
            task_id = data.get("task_id")
            if task_id and task_id in active_tasks:
                task = active_tasks[task_id]
                save_name = task.get("save_name")
                save_path = task.get("save_path")
                engine = task.get("engine", "native")
                
                if engine == "ytdlp":
                    final_dir = save_path if save_path else os.path.join(os.path.expanduser("~"), "Downloads")
                else:
                    final_dir = save_path if save_path else os.path.join(os.path.expanduser("~"), "Downloads")
                    
                final_file = os.path.join(final_dir, save_name)
                final_file = os.path.abspath(final_file)
                
                if os.path.exists(final_file):
                    try:
                        creationflags = 0
                        if os.name == 'nt':
                            creationflags = subprocess.CREATE_NO_WINDOW
                        subprocess.run(["explorer.exe", "/select,", final_file], creationflags=creationflags)
                    except Exception: pass
                    return web.json_response({"status": "opened"})
                return web.json_response({"error": "File not found"}, status=404)
            return web.json_response({"error": "Task not found"}, status=404)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_delete(request):
        try:
            data = await request.json()
            task_id = str(data.get("task_id"))
            if task_id and task_id in active_tasks:
                if task_id in running_tasks:
                    running_tasks[task_id].cancel()
                del active_tasks[task_id]
                # Save immediately
                with open(TASKS_FILE, "w", encoding="utf-8") as f:
                    json.dump(active_tasks, f)
                return web.json_response({"status": "deleted"})
            return web.json_response({"error": "Task not found"}, status=404)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    app.router.add_post('/download', handle_download)
    app.router.add_options('/download', handle_options)
    app.router.add_post('/cancel', handle_cancel)
    app.router.add_options('/cancel', handle_options)
    app.router.add_post('/delete', handle_delete)
    app.router.add_options('/delete', handle_options)
    app.router.add_post('/open_folder', handle_open_folder)
    app.router.add_options('/open_folder', handle_options)
    app.router.add_get('/status', handle_status)
    app.router.add_options('/status', handle_options)
    app.router.add_get('/stream', handle_stream)
    
    return app

def _check_ffmpeg():
    try:
        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
        logger.info("ffmpeg found: OK")
    except Exception:
        logger.error(
            "ffmpeg NOT found in PATH! Merge step will fail. "
            "Install ffmpeg and make sure it is in the system PATH."
        )

def _check_ytdlp():
    try:
        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW
        subprocess.run(["yt-dlp", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
        logger.info("yt-dlp found: OK (Fallback engine available)")
    except Exception:
        logger.warning(
            "yt-dlp NOT found in PATH! Fallback engine will fail. "
            "Install yt-dlp to support downloading encrypted/complex sites."
        )

def cleanup_old_tmp_files():
    tmp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_files")
    if not os.path.exists(tmp_dir):
        return
        
    now = time.time()
    cutoff = now - (24 * 3600)  # 24 hours ago
    
    deleted_count = 0
    for item in os.listdir(tmp_dir):
        item_path = os.path.join(tmp_dir, item)
        try:
            mtime = os.path.getmtime(item_path)
            if mtime < cutoff:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
                deleted_count += 1
        except Exception as e:
            logger.error(f"Error deleting old tmp file {item_path}: {e}")
            
    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} old temporary items from {tmp_dir}")

def main():
    _check_ffmpeg()
    _check_ytdlp()
    cleanup_old_tmp_files()
    logger.info("Starting local server on http://localhost:8000 ...")
    logger.info("Waiting for requests from the Firefox extension...")
    app = create_app()
    web.run_app(app, host='127.0.0.1', port=8000)

if __name__ == "__main__":
    main()
