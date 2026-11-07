import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Callable
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from src.comparator import FileItem, SyncStatus
from src.utils import calculate_file_hash, should_exclude

# 읽기/비교 및 업로드용 스코프
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

class GoogleDriveApiClient:
    def __init__(self, credentials_path: str = "credentials.json", token_path: str = "token.json"):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self.user_info = None
        self._is_cancelled = False

    def is_authenticated(self) -> bool:
        return self.service is not None

    def cancel(self):
        self._is_cancelled = True

    def authenticate(self, credentials_path: Optional[str] = None) -> dict:
        """OAuth 2.0 인증 수행 (브라우저 로그인 팝업 지원)"""
        if credentials_path:
            self.credentials_path = credentials_path

        creds = None
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None

            if not creds:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Google Cloud OAuth 인증 파일({self.credentials_path})이 필요합니다.\n"
                        "Google Cloud Console에서 다운로드한 credentials.json을 지정해주세요."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            # 토큰 저장
            with open(self.token_path, 'w', encoding='utf-8') as token_file:
                token_file.write(creds.to_json())

        self.service = build('drive', 'v3', credentials=creds)

        # 사용자 정보 조회
        try:
            about = self.service.about().get(fields="user(displayName, emailAddress)").execute()
            self.user_info = about.get('user', {})
        except Exception:
            self.user_info = {"displayName": "인증 완료", "emailAddress": ""}

        return self.user_info

    def search_folders(self, name_query: str = "") -> List[dict]:
        """Google Drive 웹 상에서 폴더 검색"""
        if not self.service:
            raise RuntimeError("Google Drive에 인증되지 않았습니다.")

        query = "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if name_query:
            query += f" and name contains '{name_query}'"

        results = self.service.files().list(
            q=query,
            pageSize=30,
            fields="files(id, name, parents, modifiedTime)"
        ).execute()

        return results.get('files', [])

    def fetch_all_files_in_folder(self, root_folder_id: str, progress_callback: Optional[Callable[[str], None]] = None) -> Dict[str, dict]:
        """
        특정 Google Drive 폴더 하위의 모든 파일들을 재귀적으로 수집하여 상대경로 -> 메타데이터 맵 생성
        """
        self._is_cancelled = False
        file_map: Dict[str, dict] = {}

        # 큐: (folder_id, current_rel_dir)
        queue = [(root_folder_id, "")]

        while queue:
            if self._is_cancelled:
                break
            
            curr_id, curr_rel = queue.pop(0)
            page_token = None

            while True:
                if self._is_cancelled:
                    break

                query = f"'{curr_id}' in parents and trashed = false"
                res = self.service.files().list(
                    q=query,
                    pageSize=100,
                    pageToken=page_token,
                    fields="nextPageToken, files(id, name, size, md5Checksum, modifiedTime, mimeType)"
                ).execute()

                items = res.get('files', [])
                for item in items:
                    name = item['name']
                    rel_path = f"{curr_rel}/{name}".lstrip("/") if curr_rel else name
                    mime_type = item.get('mimeType', '')

                    if mime_type == 'application/vnd.google-apps.folder':
                        queue.append((item['id'], rel_path))
                    else:
                        # Google Docs/Sheets 전용 형식은 바이너리 크기나 MD5가 없음
                        is_gdoc = mime_type.startswith('application/vnd.google-apps.')
                        size = int(item.get('size', 0)) if not is_gdoc else 0
                        md5 = item.get('md5Checksum', '')
                        
                        # ISO 8601 -> timestamp
                        mtime_str = item.get('modifiedTime', '')
                        mtime_ts = 0.0
                        if mtime_str:
                            try:
                                dt = datetime.fromisoformat(mtime_str.replace('Z', '+00:00'))
                                mtime_ts = dt.timestamp()
                            except Exception:
                                pass

                        file_map[rel_path] = {
                            'id': item['id'],
                            'name': name,
                            'size': size,
                            'md5': md5,
                            'mtime': mtime_ts,
                            'is_gdoc': is_gdoc
                        }
                        if progress_callback:
                            progress_callback(f"웹 파일 목록 수집 중: {rel_path}")

                page_token = res.get('nextPageToken')
                if not page_token:
                    break

        return file_map

    def compare_with_local(self, local_dir: str, root_folder_id: str, check_hash: bool = True, exclude_system: bool = True, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> List[FileItem]:
        """
        로컬 디렉토리와 Google Drive 웹 폴더의 파일들을 API로 직접 비교
        """
        self._is_cancelled = False
        results: List[FileItem] = []

        if not os.path.isdir(local_dir):
            raise ValueError(f"유효하지 않은 로컬 폴더입니다: {local_dir}")

        # 1. Google Drive 웹 파일 수집
        if progress_callback:
            progress_callback(0, 0, "Google Drive 웹 파일 목록을 API로 불러오는 중...")
        
        web_files = self.fetch_all_files_in_folder(
            root_folder_id, 
            progress_callback=lambda msg: progress_callback(0, 0, msg) if progress_callback else None
        )
        if self._is_cancelled:
            return []

        # 2. 로컬 파일 목록 수집
        if progress_callback:
            progress_callback(0, 0, "로컬 파일 목록 스캔 중...")

        local_files = {}
        for root, dirs, files in os.walk(local_dir):
            if self._is_cancelled:
                break
            if exclude_system:
                dirs[:] = [d for d in dirs if not should_exclude(d)]

            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, local_dir).replace("\\", "/")
                if exclude_system and should_exclude(rel_path):
                    continue
                try:
                    local_files[rel_path] = os.stat(full_path)
                except Exception:
                    pass

        # 3. 파일 대조
        all_paths = sorted(list(set(local_files.keys()).union(set(web_files.keys()))))
        total_files = len(all_paths)

        for index, rel_path in enumerate(all_paths):
            if self._is_cancelled:
                break

            l_stat = local_files.get(rel_path)
            w_file = web_files.get(rel_path)

            if progress_callback:
                progress_callback(index + 1, total_files, f"웹 서버와 대조 중 ({index+1}/{total_files}): {rel_path}")

            if l_stat and not w_file:
                # 로컬에만 있음 -> 웹 업로드 누락!
                results.append(FileItem(
                    rel_path=rel_path,
                    status=SyncStatus.MISSING_IN_GDRIVE,
                    local_size=l_stat.st_size,
                    local_mtime=l_stat.st_mtime,
                    detail="로컬에만 존재함 (Google Drive 웹에 업로드되지 않음)"
                ))
            elif not l_stat and w_file:
                # 웹에만 있음
                results.append(FileItem(
                    rel_path=rel_path,
                    status=SyncStatus.EXTRA_IN_GDRIVE,
                    gdrive_size=w_file['size'],
                    gdrive_mtime=w_file['mtime'],
                    detail=f"Google Drive 웹에만 존재함 (ID: {w_file['id'][:8]}...)"
                ))
            else:
                l_size = l_stat.st_size
                w_size = w_file['size']
                l_mtime = l_stat.st_mtime
                w_mtime = w_file['mtime']
                w_md5 = w_file.get('md5', '')
                is_gdoc = w_file.get('is_gdoc', False)

                # 구글 문서(Docs/Sheets 등)는 크기/MD5 비교 제외
                if is_gdoc:
                    results.append(FileItem(
                        rel_path=rel_path,
                        status=SyncStatus.SYNCED,
                        local_size=l_size,
                        detail="Google 온라인 전용 문서 형식 (동기화 완료)"
                    ))
                    continue

                # 크기 비교
                if l_size != w_size:
                    results.append(FileItem(
                        rel_path=rel_path,
                        status=SyncStatus.SIZE_MISMATCH,
                        local_size=l_size,
                        local_mtime=l_mtime,
                        gdrive_size=w_size,
                        gdrive_mtime=w_mtime,
                        detail=f"크기 불일치 (로컬: {l_size} B vs 웹: {w_size} B)"
                    ))
                    continue

                # 해시 검사 (Google Drive API는 원본 파일의 MD5 해시를 기본 제공함)
                if check_hash and w_md5:
                    l_full = os.path.join(local_dir, rel_path.replace("/", "\\"))
                    l_hash = calculate_file_hash(l_full)
                    if l_hash.lower() != w_md5.lower():
                        results.append(FileItem(
                            rel_path=rel_path,
                            status=SyncStatus.HASH_MISMATCH,
                            local_size=l_size,
                            local_mtime=l_mtime,
                            gdrive_size=w_size,
                            gdrive_mtime=w_mtime,
                            local_hash=l_hash,
                            gdrive_hash=w_md5,
                            detail="내용(MD5 해시) 불일치"
                        ))
                        continue

                results.append(FileItem(
                    rel_path=rel_path,
                    status=SyncStatus.SYNCED,
                    local_size=l_size,
                    local_mtime=l_mtime,
                    gdrive_size=w_size,
                    gdrive_mtime=w_mtime,
                    gdrive_hash=w_md5,
                    detail="Google Drive 웹과 일치함"
                ))

        return results
