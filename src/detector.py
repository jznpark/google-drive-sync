import os
from typing import List, Tuple

def detect_sync_pairs() -> List[Tuple[str, str, str]]:
    """
    PC에서 Google Drive와 동기화 중인 로컬 폴더 및 가상 드라이브 경로 쌍을 자동 감지
    반환: [(표시이름, 로컬경로, 구글드라이브경로), ...]
    """
    pairs = []
    
    # 1. '내 컴퓨터' 동기화 폴더 감지 (G:\다른 컴퓨터\내 컴퓨터\...)
    candidates_other = [
        r"G:\다른 컴퓨터\내 컴퓨터",
        r"G:\Other computers\My Computer",
        r"G:\Computers\My Computer"
    ]
    
    drives_to_search = ["C:\\", "D:\\", "E:\\", os.path.expanduser("~")]

    for g_other in candidates_other:
        if os.path.exists(g_other):
            try:
                for item in os.listdir(g_other):
                    g_path = os.path.join(g_other, item)
                    if os.path.isdir(g_path):
                        # 매칭되는 로컬 폴더 탐색
                        matched_local = None
                        for d in drives_to_search:
                            cand = os.path.join(d, item)
                            if os.path.exists(cand) and os.path.isdir(cand):
                                matched_local = cand
                                break
                        
                        if matched_local:
                            pairs.append((f"[내 컴퓨터] {item}", matched_local, g_path))
                        else:
                            pairs.append((f"[내 컴퓨터] {item} (로컬 미확인)", "", g_path))
            except Exception:
                pass

    # 2. '내 드라이브' (G:\내 드라이브)
    candidates_my = [
        r"G:\내 드라이브",
        r"G:\My Drive",
        "G:\\"
    ]
    for g_my in candidates_my:
        if os.path.exists(g_my):
            pairs.append(("[내 드라이브] 전체 루트", "", g_my))
            break

    return pairs
