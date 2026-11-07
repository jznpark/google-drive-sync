import os
import shutil
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable

from src.utils import format_size, format_time, calculate_file_hash, should_exclude

class SyncStatus(Enum):
    SYNCED = "동기화 완료"
    MISSING_IN_GDRIVE = "구글드라이브 누락"
    EXTRA_IN_GDRIVE = "로컬 누락 (드라이브 전용)"
    SIZE_MISMATCH = "파일 크기 불일치"
    TIME_MISMATCH = "수정 시간 불일치"
    HASH_MISMATCH = "내용(해시) 불일치"
    ERROR = "오류"

@dataclass
class FileItem:
    rel_path: str
    status: SyncStatus
    local_size: int = -1
    local_mtime: float = 0.0
    gdrive_size: int = -1
    gdrive_mtime: float = 0.0
    local_hash: str = ""
    gdrive_hash: str = ""
    detail: str = ""

    @property
    def is_problematic(self) -> bool:
        return self.status in {
            SyncStatus.MISSING_IN_GDRIVE,
            SyncStatus.SIZE_MISMATCH,
            SyncStatus.TIME_MISMATCH,
            SyncStatus.HASH_MISMATCH,
            SyncStatus.ERROR
        }

class SyncComparator:
    def __init__(self, local_dir: str, gdrive_dir: str, check_hash: bool = False, exclude_system: bool = True):
        self.local_dir = os.path.abspath(local_dir)
        self.gdrive_dir = os.path.abspath(gdrive_dir)
        self.check_hash = check_hash
        self.exclude_system = exclude_system
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def scan_directory(self, base_dir: str, progress_callback: Optional[Callable[[str], None]] = None) -> Dict[str, os.stat_result]:
        """디렉토리를 재귀적으로 스캔하여 상대경로 -> stat_result 맵 반환"""
        file_map = {}
        if not os.path.exists(base_dir):
            return file_map

        for root, dirs, files in os.walk(base_dir):
            if self._is_cancelled:
                break
            
            # 무시할 디렉토리 필터링
            if self.exclude_system:
                dirs[:] = [d for d in dirs if not should_exclude(d)]

            for file in files:
                if self._is_cancelled:
                    break
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base_dir).replace("\\", "/")
                
                if self.exclude_system and should_exclude(rel_path):
                    continue

                try:
                    stat = os.stat(full_path)
                    file_map[rel_path] = stat
                    if progress_callback:
                        progress_callback(f"스캔 중: {rel_path}")
                except Exception as e:
                    pass

        return file_map

    def compare(self, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> List[FileItem]:
        """로컬 폴더와 구글 드라이브 폴더를 비교 분석"""
        self._is_cancelled = False
        results: List[FileItem] = []

        if not os.path.isdir(self.local_dir):
            raise ValueError(f"로컬 폴더가 존재하지 않거나 올바르지 않습니다: {self.local_dir}")
        if not os.path.isdir(self.gdrive_dir):
            raise ValueError(f"Google Drive 폴더가 존재하지 않거나 올바르지 않습니다: {self.gdrive_dir}")

        # 1. 파일 목록 스캔
        if progress_callback:
            progress_callback(0, 0, "로컬 폴더 파일 목록 스캔 중...")
        local_files = self.scan_directory(self.local_dir)
        if self._is_cancelled:
            return []

        if progress_callback:
            progress_callback(0, 0, "Google Drive 폴더 파일 목록 스캔 중...")
        gdrive_files = self.scan_directory(self.gdrive_dir)
        if self._is_cancelled:
            return []

        # 모든 고유 상대 경로 수집
        all_paths = sorted(list(set(local_files.keys()).union(set(gdrive_files.keys()))))
        total_files = len(all_paths)

        # 2. 비교 수행
        for index, rel_path in enumerate(all_paths):
            if self._is_cancelled:
                break

            local_stat = local_files.get(rel_path)
            gdrive_stat = gdrive_files.get(rel_path)

            if progress_callback:
                progress_callback(index + 1, total_files, f"비교 중 ({index+1}/{total_files}): {rel_path}")

            if local_stat and not gdrive_stat:
                results.append(FileItem(
                    rel_path=rel_path,
                    status=SyncStatus.MISSING_IN_GDRIVE,
                    local_size=local_stat.st_size,
                    local_mtime=local_stat.st_mtime,
                    detail="로컬에만 존재함 (Google Drive로 아직 동기화되지 않음)"
                ))
            elif not local_stat and gdrive_stat:
                results.append(FileItem(
                    rel_path=rel_path,
                    status=SyncStatus.EXTRA_IN_GDRIVE,
                    gdrive_size=gdrive_stat.st_size,
                    gdrive_mtime=gdrive_stat.st_mtime,
                    detail="Google Drive에만 존재함 (로컬에 없음)"
                ))
            else:
                # 둘 다 존재하는 경우
                l_size = local_stat.st_size
                g_size = gdrive_stat.st_size
                l_mtime = local_stat.st_mtime
                g_mtime = gdrive_stat.st_mtime

                # 크기 비교
                if l_size != g_size:
                    results.append(FileItem(
                        rel_path=rel_path,
                        status=SyncStatus.SIZE_MISMATCH,
                        local_size=l_size,
                        local_mtime=l_mtime,
                        gdrive_size=g_size,
                        gdrive_mtime=g_mtime,
                        detail=f"크기 차이 (로컬: {format_size(l_size)} vs Drive: {format_size(g_size)})"
                    ))
                    continue

                # 해시 검사 옵션이 켜진 경우
                if self.check_hash:
                    l_full = os.path.join(self.local_dir, rel_path.replace("/", "\\"))
                    g_full = os.path.join(self.gdrive_dir, rel_path.replace("/", "\\"))
                    l_hash = calculate_file_hash(l_full)
                    g_hash = calculate_file_hash(g_full)

                    if l_hash != g_hash:
                        results.append(FileItem(
                            rel_path=rel_path,
                            status=SyncStatus.HASH_MISMATCH,
                            local_size=l_size,
                            local_mtime=l_mtime,
                            gdrive_size=g_size,
                            gdrive_mtime=g_mtime,
                            local_hash=l_hash,
                            gdrive_hash=g_hash,
                            detail="내용(MD5 해시)이 일치하지 않음"
                        ))
                        continue

                # 수정 시간 비교 (2초 이상 차이날 경우에만 경고 - 파일시스템 시간 정밀도 차이 방지)
                time_diff = abs(l_mtime - g_mtime)
                if time_diff > 3.0:
                    results.append(FileItem(
                        rel_path=rel_path,
                        status=SyncStatus.TIME_MISMATCH,
                        local_size=l_size,
                        local_mtime=l_mtime,
                        gdrive_size=g_size,
                        gdrive_mtime=g_mtime,
                        detail=f"수정 시각 차이 ({time_diff:.1f}초 차이)"
                    ))
                else:
                    results.append(FileItem(
                        rel_path=rel_path,
                        status=SyncStatus.SYNCED,
                        local_size=l_size,
                        local_mtime=l_mtime,
                        gdrive_size=g_size,
                        gdrive_mtime=g_mtime,
                        detail="동기화 정상 완료"
                    ))

        return results

    def sync_to_gdrive(self, items: List[FileItem], progress_callback: Optional[Callable[[int, int, str], None]] = None) -> int:
        """선택한 로컬 파일들을 Google Drive 대상 폴더로 복사/덮어쓰기하여 수동 동기화"""
        self._is_cancelled = False
        success_count = 0
        total = len(items)

        for index, item in enumerate(items):
            if self._is_cancelled:
                break
            
            src_path = os.path.join(self.local_dir, item.rel_path.replace("/", "\\"))
            dst_path = os.path.join(self.gdrive_dir, item.rel_path.replace("/", "\\"))

            if not os.path.exists(src_path):
                continue

            if progress_callback:
                progress_callback(index + 1, total, f"복사 중 ({index+1}/{total}): {item.rel_path}")

            try:
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)
                success_count += 1
            except Exception as e:
                print(f"복사 실패 ({item.rel_path}): {e}")

        return success_count
