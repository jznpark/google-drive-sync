import os
import hashlib
from datetime import datetime
from pathlib import Path

# 기본 제외 패턴
DEFAULT_EXCLUDE_NAMES = {
    ".git", ".svn", ".hg", "__pycache__", ".venv", "node_modules",
    "desktop.ini", "Thumbs.db", ".DS_Store", "Icon\r", "$RECYCLE.BIN"
}

def format_size(size_bytes: int) -> str:
    """바이트 크기를 사람이 읽기 쉬운 문자열(KB, MB, GB 등)로 변환"""
    if size_bytes < 0:
        return "-"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0 or unit == 'TB':
            return f"{size_bytes:.2f} {unit}" if unit != 'B' else f"{size_bytes} B"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def format_time(timestamp: float) -> str:
    """타임스탬프를 'YYYY-MM-DD HH:MM:SS' 형식으로 변환"""
    if not timestamp or timestamp <= 0:
        return "-"
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "-"

def calculate_file_hash(filepath: str, chunk_size: int = 1024 * 1024) -> str:
    """대용량 파일도 메모리 부담 없이 MD5 해시를 청크 단위로 계산"""
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        return f"ERROR: {str(e)}"

def should_exclude(rel_path: str) -> bool:
    """임시 파일, 시스템 파일, 숨김 메타데이터 제외 여부 판단"""
    parts = Path(rel_path).parts
    for part in parts:
        if part in DEFAULT_EXCLUDE_NAMES:
            return True
        if part.startswith("~$") or part.endswith(".tmp"):
            return True
    return False
