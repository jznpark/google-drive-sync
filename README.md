# 🔍 Google Drive 동기화 상태 검사기 (Sync Checker) v2.0

Google Drive 데스크톱 앱(가상 `G:\` 드라이브) 및 Google Drive 공식 REST API를 활용하여, 로컬 PC에서 작업한 파일들이 Google Drive 상으로 정상적으로 동기화(업로드)되었는지 직관적으로 확인하고 수동으로 동기화를 맞출 수 있는 미니 데스크톱 프로그램입니다.

---

## ✨ v2.0 새로운 기능

### 1. ⚡ 동기화 폴더 자동 감지 (Auto-Detect)
- PC에 설정된 Google Drive "컴퓨터의 폴더 백업/동기화" 대상을 프로그램 시작 시 자동 감지합니다.
- 예: `C:\LabDrive` ↔ `G:\다른 컴퓨터\내 컴퓨터\LabDrive`
- 사용자가 복잡한 경로를 찾을 필요 없이 상단 드롭다운에서 선택만 하면 경로가 자동 입력됩니다.

### 2. 🌐 2가지 검사 방식 지원
* **[모드 A] 가상 드라이브 모드 (G:\ 빠른 대조)**:
  * 별도 인증이나 API 설정 없이 지금 즉시 초고속으로 검사합니다.
  * Windows 가상 드라이브에 마운트된 웹 동기화 상태를 기준으로 대조합니다.
* **[모드 B] Google Drive 공식 Web API 모드 (실시간 웹 대조)**:
  * Google Cloud REST API를 통해 웹(`drive.google.com`) 서버에 직접 질의합니다.
  * 구글 서버에 저장된 실제 메타데이터(`md5Checksum`, `size`, `modifiedTime`)와 로컬을 1:1 대조합니다.

---

## ✨ 핵심 기능

1. **상태 자동 판별 & 시각화**:
   - 🔴 **구글드라이브 누락**: 로컬에는 존재하지만 Google Drive에는 아직 업로드되지 않은 파일
   - 🟡 **불일치**: 파일명은 같으나 크기, 최종 수정 시각, 또는 내용(MD5 해시)이 다른 파일
   - 🟢 **동기화 완료**: 웹/드라이브와 완벽하게 일치하는 파일
   - ⚪ **드라이브 전용**: Google Drive에만 있는 파일
2. **정밀 검사 (MD5 체크섬 대조)**:
   - 파일 크기뿐만 아니라 바이너리 내용까지 청크 단위로 100% 무결성 검증
3. **🚀 원클릭 동기화 (복사) 지원**:
   - 누락되거나 수정된 파일들을 Google Drive 대상 위치로 폴더 구조 그대로 한 번에 복사하여 Google Drive 데스크톱 앱의 자동 업로드를 즉시 유도
4. **검색 & 필터링 & CSV 리포트 내보내기**:
   - 문제 있는 파일(누락/불일치)만 모아보기
   - 파일명 실시간 검색 및 CSV 저장

---

## 🚀 빠른 실행 방법

### 방법 1. 더블 클릭 실행 (가장 간단)
프로젝트 폴더 내의 **`run.bat`** 파일을 더블 클릭하면 자동으로 실행됩니다.

### 방법 2. 파이썬 가상환경 직접 실행
```bash
cd C:\Workspace\google-drive-sync
.\.venv\Scripts\python.exe main.py
```

---

## 🔑 (선택) Google Drive Web API 모드 설정 방법

> [!NOTE]
> 일반적인 검사는 **[가상 드라이브 모드]** 만으로도 API 설정 없이 100% 충분합니다. 웹 서버에 직접 통신하는 API 모드를 쓰고 싶으실 때만 아래 설정을 진행하세요.

1. [Google Cloud Console](https://console.cloud.google.com/) 접속 및 새 프로젝트 생성
2. **API 및 서비스 > 라이브러리**에서 `Google Drive API` 검색 후 **[사용]** 클릭
3. **API 및 서비스 > OAuth 동의 화면** 설정 (User Type: 외부, 테스트 사용자 등록)
4. **사용자 인증 정보 > 사용자 인증 정보 만들기 > OAuth 클라이언트 ID**:
   - 애플리케이션 유형: **데스크톱 앱 (Desktop app)**
5. JSON 다운로드 후 파일명을 **`credentials.json`** 으로 변경하여 `C:\Workspace\google-drive-sync\` 폴더에 복사
6. 프로그램에서 **[Google 계정 로그인 / 인증]** 클릭 시 브라우저에서 1회 로그인 완료!

---

## 🛠 기술 스택
- **Language**: Python 3.11
- **GUI Framework**: CustomTkinter 6.0
- **API**: Google Drive REST API v3 (`google-api-python-client`)
- **Table**: ttk.Treeview
- **Async Threading**: UI 멈춤 방지 멀티스레드 아키텍처

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
│   ├── detector.py     # 로컬 ↔ Google Drive 동기화 폴더 자동 감지
│   ├── gdrive_api.py   # Google Drive REST API 클라이언트
│   ├── gui.py          # CustomTkinter 기반 데스크톱 UI
│   └── utils.py        # 포맷팅, MD5 해시, 시스템 파일 필터
└── README.md           # 문서
```
