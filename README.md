# 🔍 Google Drive 동기화 상태 검사기 (Sync Checker) v2.1

Google Drive 데스크톱 앱(가상 `G:\` 드라이브) 및 Google Drive 공식 REST API를 활용하여, PC의 Google Drive 폴더에 저장된 파일들이 실제 Google Drive 웹 서버(클라우드) 상으로 정상적으로 동기화(업로드)되었는지 직관적으로 확인하는 미니 데스크톱 프로그램입니다.

---

## ✨ v2.1 업데이트: 간결해진 단일 폴더 검사 모드

### 🌐 Google Drive 웹 동기화 검사 (단일 폴더 모드) [기본값]
* PC의 로컬 디스크(`C:\` 등)를 지정할 필요 없이, **PC에서 작업 중인 Google Drive 폴더(`G:\...`) 단 하나만 선택**하면 됩니다.
* 선택한 폴더의 실제 파일들과 Google Drive 공식 Web API(실시간 클라우드 서버)를 직접 대조하여 다음 상태를 정확하게 추출합니다:
  * 🔴 **웹 업로드 누락**: PC의 G: 드라이브에는 저장되어 있으나, 구글 웹 클라우드 서버에는 아직 올라가지 않은 미동기화 파일
  * 🟡 **불일치**: 크기나 내용(MD5 해시)이 클라우드 서버와 다른 파일
  * 🟢 **정상 동기화**: PC와 구글 웹 서버가 100% 온전히 일치하는 파일
  * ⚪ **웹 전용**: 웹 클라우드 서버에만 존재하는 파일

### 📁 2개 폴더 간 대조 모드 (선택 사항)
* 로컬 PC 일반 폴더(예: `C:\MyWork`)와 Google Drive 대상 폴더 간의 복사/백업 여부를 비교할 때 사용할 수 있습니다.

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

## 🛠 기술 스택
- **Language**: Python 3.11
- **GUI Framework**: CustomTkinter 6.0
- **API**: Google Drive REST API v3 (`google-api-python-client`)
- **Table**: ttk.Treeview
- **Async Threading**: UI 멈춤 방지 멀티스레드 아키텍처
