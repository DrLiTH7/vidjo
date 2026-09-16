import os
import re
import sys
import shutil


def ensure_scripts_in_path():
    """Ensure Python scripts/bin and project venv are in the process PATH."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dirs_to_add = [
        os.path.dirname(sys.executable),
        os.path.join(base_dir, "venv", "Scripts"),
        os.path.join(base_dir, ".venv", "Scripts"),
        os.path.join(base_dir, "venv", "bin"),
        os.path.join(base_dir, ".venv", "bin"),
    ]
    current_path = os.environ.get("PATH", "")
    path_dirs = [os.path.normpath(p).lower() for p in current_path.split(os.pathsep) if p]

    new_dirs = []
    for d in dirs_to_add:
        if os.path.isdir(d) and os.path.normpath(d).lower() not in path_dirs and d not in new_dirs:
            new_dirs.append(d)

    if new_dirs:
        os.environ["PATH"] = os.pathsep.join(new_dirs) + (os.pathsep + current_path if current_path else "")


def get_binary_path(name: str) -> str:
    """Find the executable path for a given binary (e.g. ffmpeg or yt-dlp)."""
    ensure_scripts_in_path()
    found = shutil.which(name)
    if found:
        return found

    base_dir = os.path.dirname(os.path.abspath(__file__))
    exts = [".exe", ""] if os.name == "nt" else [""]
    search_dirs = [
        os.path.dirname(sys.executable),
        os.path.join(base_dir, "venv", "Scripts"),
        os.path.join(base_dir, ".venv", "Scripts"),
        os.path.join(base_dir, "venv", "bin"),
        os.path.join(base_dir, ".venv", "bin"),
    ]
    for d in search_dirs:
        for ext in exts:
            candidate = os.path.join(d, f"{name}{ext}")
            if os.path.isfile(candidate):
                return candidate

    return name


# Ensure PATH is configured upon import
ensure_scripts_in_path()


def get_url_basename(url: str) -> str:
    """Get the basename of the URL without query parameters"""
    path = url.split("?")[0].rstrip("/")
    return os.path.basename(path)


def sanitize_filename(name: str) -> str:
    """Remove or replace characters that are invalid for filenames across OSs"""
    if not name:
        return name
        
    # Remove zero-width characters and format characters
    name = re.sub(r'[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]', '', name)
    
    # Replace invalid Windows/Linux/Mac filename characters and control characters with an underscore
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f-\x9f]', '_', name)
    
    # Remove leading/trailing spaces and dots
    name = name.strip(' .')
    
    # Handle Windows reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    reserved = r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$'
    if re.match(reserved, name, flags=re.IGNORECASE):
        name = f"_{name}"
        
    # Fallback if name is empty after strip
    if not name:
        name = "unnamed_video"
        
    return name
