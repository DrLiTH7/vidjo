import os
import re


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
