# 🔍 Google Drive 동기화 상태 검사기 (Sync Checker)

Google Drive 데스크톱 앱(가상 `G:\` 드라이브)을 사용할 때, 로컬 PC에서 작업한 파일들이 Google Drive 상으로 정상적으로 동기화(업로드)되었는지 직관적으로 확인하고 수동으로 동기화를 맞출 수 있는 미니 데스크톱 프로그램입니다.

---

## ✨ 주요 기능

1. **상태 자동 판별 & 시각화**:
   - 🔴 **구글드라이브 누락**: 로컬에는 존재하지만 Google Drive에는 아직 없는 미동기화 파일
   - 🟡 **불일치**: 파일명은 같으나 크기, 최종 수정 시각, 또는 내용 해시가 다른 파일
   - 🟢 **동기화 완료**: 완벽하게 일치하는 파일
   - ⚪ **드라이브 전용**: Google Drive에만 있는 파일
2. **다양한 검사 옵션**:
   - **빠른 검사**: 파일 크기 및 수정 시각 기준 (수천 개 파일도 몇 초 만에 완료)
   - **정밀 검사 (MD5 해시)**: 대용량 파일도 청크 단위로 파일 내용을 100% 대조
   - **시스템/임시 파일 필터링**: `.git`, `desktop.ini`, `Thumbs.db`, `~$*` 임시 파일 자동 제외
3. **🚀 원클릭 동기화 (복사) 지원**:
   - 누락되거나 수정된 파일들을 Google Drive 대상 위치로 폴더 구조 그대로 한 번에 복사하여 Google Drive 데스크톱 앱의 자동 업로드를 즉시 유도
4. **검색 & 필터링 & CSV 리포트 내보내기**:
   - 문제 있는 파일(누락/불일치)만 모아보기
   - 파일명 실시간 검색
   - 결과를 CSV 파일로 내보내기

---

## 🚀 빠른 실행 방법

### 방법 1. 더블 클릭 실행 (가장 간단)
프로젝트 폴더 내의 **`run.bat`** 파일을 더블 클릭하면 자동으로 실행됩니다.

### 방법 2. 파이썬 가상환경 직접 실행
```bash
# 가상환경 활성화
.\.venv\Scripts\activate

# 프로그램 실행
python main.py
```

---

## 🛠 기술 스택
- **Language**: Python 3.11
- **GUI Framework**: CustomTkinter 6.0 (모던 다크/라이트 테마 자동 지원)
- **Table**: ttk.Treeview (대량의 파일도 렉 없이 부드럽게 렌더링)
- **Async Threading**: 대용량 스캔 중에도 GUI가 멈추지 않는 멀티스레드 아키텍처

---

## 📂 프로젝트 구조
```
C:\Workspace\google-drive-sync\
├── .gitignore          # Git 제외 목록
├── requirements.txt    # 의존성 목록
├── run.bat             # 원클릭 실행 배치 파일
├── main.py             # 프로그램 진입점
├── src\
│   ├── comparator.py   # 폴더 스캔, 파일 비교, 해시 계산 및 복사 로직
│   ├── gui.py          # CustomTkinter 기반 데스크톱 UI
│   └── utils.py        # 파일 크기/시간 포맷팅, MD5 해시 유틸
└── README.md           # 문서
```

---

## 🐙 GitHub에 올리는 방법

원격 리포지토리에 올리고 싶으시다면 터미널에서 다음 명령어를 실행하시면 됩니다:
```bash
git remote add origin https://github.com/사용자계정/리포지토리이름.git
git branch -M main
git push -u origin main
```
