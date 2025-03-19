import hashlib
import json
import os
from typing import Dict

def get_file_md5(file_path: str) -> str:
    """Calculate MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def get_text_md5(text: str) -> str:
    """Calculate MD5 hash of a text string."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def load_translation_cache(cache_file: str) -> Dict[str, Dict[str, str]]:
    """Load translation cache from JSON file."""
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load cache file: {e}")
    return {}

def save_translation_cache(cache_file: str, cache: Dict[str, Dict[str, str]]) -> None:
    """Save translation cache to JSON file."""
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save cache file: {e}")
