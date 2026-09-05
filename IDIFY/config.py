# ==========================================================
# PASTE THE CODE COPIED FROM THE FIREFOX EXTENSION BELOW
# ==========================================================
BlobUrls = [
    (
        "https://id=16457598",
        "video.mp4",
    ),
]

HeaderConfig = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:151.0) Gecko/20100101 Firefox/151.0",
    "origin": "https://www.exemple.com",
    "referer": "https://www.exemple.com/",
}

# ==========================================================
# END OF EXTENSION PASTE AREA
# ==========================================================

DownloaderConfig = {
    "max_retry": 3,       # retry attempts on connection errors
    "max_concurrent": 20, # total simultaneous segment downloads
}

FfmpegConfig = {
    # Number of CPU threads ffmpeg can use during merge.
    # 0 = let ffmpeg decide automatically (uses all available cores).
    # Example: set to 4 to limit CPU usage on a 16-core machine.
    "threads": 0,
}

GetConfig = {
    # "proxy": "http://127.0.0.1:7897",
}

# limit=0 removes the global cap so limit_per_host becomes the only constraint,
# matching max_concurrent and preventing the old mismatch where limit=5 made
# the semaphore of 20 irrelevant.
ConnectorConfig = {
    "verify_ssl": True,
    "limit": 0,
    "limit_per_host": 20,
}
