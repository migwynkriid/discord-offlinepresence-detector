"""Shared utilities for the Discord bot."""
import json
import logging
import os
import threading

_file_lock = threading.Lock()


def load_json_file(filepath: str, default: dict = None) -> dict:
    """
    Safely load a JSON file with error handling.
    
    Args:
        filepath: Path to the JSON file
        default: Default value to return if file doesn't exist or is invalid
        
    Returns:
        Parsed JSON data or default value
    """
    if default is None:
        default = {}
    
    try:
        with _file_lock:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except FileNotFoundError:
        logging.warning(f"{filepath} not found, using default")
        return default
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in {filepath}: {e}")
        return default
    except Exception as e:
        logging.error(f"Error loading {filepath}: {e}")
        return default


def save_json_file(filepath: str, data: dict) -> bool:
    """
    Safely save data to a JSON file using atomic write.
    
    Args:
        filepath: Path to the JSON file
        data: Data to save
        
    Returns:
        True if successful, False otherwise
    """
    temp_path = f"{filepath}.tmp"
    try:
        with _file_lock:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            # Atomic rename
            if os.path.exists(filepath):
                os.replace(temp_path, filepath)
            else:
                os.rename(temp_path, filepath)
        return True
    except Exception as e:
        logging.error(f"Failed to save {filepath}: {e}")
        # Clean up temp file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        return False


def format_time(seconds: float) -> str:
    """
    Format seconds into human-readable time string.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted string like "1h 22m"
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours == 0:
        parts.append(f"{minutes}m")
    
    return ' '.join(parts)


# Constants
FILE_SIZE_LIMIT = 8 * 1024 * 1024  # 8MB Discord limit for non-nitro
MESSAGE_CHAR_LIMIT = 1900  # Leave some margin from Discord's 2000 limit
