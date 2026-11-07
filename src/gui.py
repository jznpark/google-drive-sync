import os
import csv
import threading
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk

from src.comparator import SyncComparator, SyncStatus, FileItem
from src.gdrive_api import GoogleDriveApiClient
from src.detector import detect_sync_pairs
from src.utils import format_size, format_time

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class SyncCheckerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Google Drive 동기화 상태 검사기 (Sync Checker) v2.1")
        self.geometry("1120x820")
        self.minsize(980, 680)

        # 상태 변수
        self.comparator = None
        self.api_client = GoogleDriveApiClient()
        self.scan_thread = None
        self.all_results: list[FileItem] = []
        self.filtered_results: list[FileItem] = []
        self.detected_pairs: list[tuple[str, str, str]] = []

        self._build_ui()
        self._load_auto_detected_pairs()
        self._check_existing_api_token()
        self._on_mode_change(self.mode_segment.get())

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # 0. 자동 감지 퀵 바
        detect_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=("#E2E8F0", "#1E293B"))
        detect_frame.grid(row=0, column=0, padx=15, pady=(12, 6), sticky="ew")
        detect_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            detect_frame, 
            text="⚡ 감지된 동기화 폴더:", 
            font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, padx=(15, 10), pady=8, sticky="w")

        self.detected_combobox = ctk.CTkComboBox(
            detect_frame,
            values=["동기화 폴더 검색 중..."],
            width=380,
            command=self._on_detected_pair_selected
        )
        self.detected_combobox.grid(row=0, column=1, padx=(0, 10), pady=8, sticky="w")

        btn_refresh_detect = ctk.CTkButton(
            detect_frame,
            text="🔄 다시 감지",
            width=90,
            command=self._load_auto_detected_pairs
        )
        btn_refresh_detect.grid(row=0, column=2, padx=(0, 15), pady=8, sticky="e")

        # 1. 검사 방식 선택 세그먼트
        mode_container = ctk.CTkFrame(self, corner_radius=10)
        mode_container.grid(row=1, column=0, padx=15, pady=(0, 8), sticky="ew")
        mode_container.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(mode_container, text="검사 방식 선택:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=15, pady=8, sticky="w"
        )

        self.mode_segment = ctk.CTkSegmentedButton(
            mode_container,
            values=[
                "🌐 Google Drive 웹 동기화 검사 (PC G: 드라이브 ↔ 웹 서버 직접 대조)",
                "📁 2개 폴더 간 대조 (로컬 PC 폴더 ↔ Google Drive 폴더)"
            ],
            command=self._on_mode_change
        )
        self.mode_segment.set("🌐 Google Drive 웹 동기화 검사 (PC G: 드라이브 ↔ 웹 서버 직접 대조)")
        self.mode_segment.grid(row=0, column=1, padx=15, pady=8, sticky="ew")

        # 2. 경로 입력 프레임
        self.input_frame = ctk.CTkFrame(self, corner_radius=10)
        self.input_frame.grid(row=2, column=0, padx=15, pady=(0, 8), sticky="ew")
        self.input_frame.grid_columnconfigure(1, weight=1)

        # [단일 폴더 모드용] PC의 Google Drive 폴더
        self.lbl_single_path = ctk.CTkLabel(self.input_frame, text="PC의 Google Drive 폴더:", font=ctk.CTkFont(weight="bold"))
        self.lbl_single_path.grid(row=0, column=0, padx=15, pady=(12, 6), sticky="w")

        self.single_path_entry = ctk.CTkEntry(
            self.input_frame, 
            placeholder_text="검사할 PC의 Google Drive 폴더 (예: G:\\다른 컴퓨터\\내 컴퓨터\\LabDrive 또는 G:\\내 드라이브)"
        )
        self.single_path_entry.grid(row=0, column=1, padx=(0, 10), pady=(12, 6), sticky="ew")

        self.btn_browse_single = ctk.CTkButton(self.input_frame, text="폴더 선택", width=90, command=self._browse_single)
        self.btn_browse_single.grid(row=0, column=2, padx=(0, 15), pady=(12, 6))

        # [2개 폴더 모드용 - 평소엔 숨김] 로컬 원본 & Google Drive 대상
        self.lbl_local_path = ctk.CTkLabel(self.input_frame, text="로컬 원본 폴더:", font=ctk.CTkFont(weight="bold"))
        self.local_path_entry = ctk.CTkEntry(self.input_frame, placeholder_text="로컬 PC 원본 폴더 (예: C:\\MyWork)")
        self.btn_browse_local = ctk.CTkButton(self.input_frame, text="폴더 선택", width=90, command=self._browse_local)

        self.lbl_gdrive_target = ctk.CTkLabel(self.input_frame, text="Google Drive 대상 폴더:", font=ctk.CTkFont(weight="bold"))
        self.gdrive_path_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Google Drive 대상 폴더 (예: G:\\내 드라이브\\MyWork)")
        self.btn_browse_gdrive = ctk.CTkButton(self.input_frame, text="드라이브 선택", width=90, command=self._browse_gdrive)

        # API 인증 상태 바
        self.api_status_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        self.api_status_frame.grid(row=1, column=0, columnspan=3, padx=15, pady=(4, 10), sticky="ew")
        self.api_status_frame.grid_columnconfigure(0, weight=1)

        self.lbl_api_auth = ctk.CTkLabel(self.api_status_frame, text="API 인증 상태: 확인 중...", text_color="gray")
        self.lbl_api_auth.grid(row=0, column=0, sticky="w")

        self.btn_api_auth = ctk.CTkButton(self.api_status_frame, text="🔑 Google 계정 로그인 / 재인증", width=190, command=self._authenticate_api)
        self.btn_api_auth.grid(row=0, column=1, padx=5, sticky="e")

        # 3. 옵션 & 컨트롤 버튼
        control_frame = ctk.CTkFrame(self, corner_radius=10)
        control_frame.grid(row=3, column=0, padx=15, pady=(0, 8), sticky="ew")
        control_frame.grid_columnconfigure(2, weight=1)

        self.hash_check_var = ctk.BooleanVar(value=True)
        self.hash_checkbox = ctk.CTkCheckBox(
            control_frame, 
            text="정밀 검사 (MD5 해시 대조 - 클라우드 내용과 100% 일치 확인)", 
            variable=self.hash_check_var
        )
        self.hash_checkbox.grid(row=0, column=0, padx=15, pady=10, sticky="w")

        self.exclude_system_var = ctk.BooleanVar(value=True)
        self.exclude_checkbox = ctk.CTkCheckBox(
            control_frame, 
            text="임시/시스템 파일 제외 (.git, desktop.ini 등)", 
            variable=self.exclude_system_var
        )
        self.exclude_checkbox.grid(row=0, column=1, padx=15, pady=10, sticky="w")

        btn_container = ctk.CTkFrame(control_frame, fg_color="transparent")
        btn_container.grid(row=0, column=2, padx=15, pady=10, sticky="e")

        self.btn_start = ctk.CTkButton(
            btn_container, 
            text="🔍 동기화 검사 시작", 
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#1f538d",
            hover_color="#14375e",
            command=self._start_scan
        )
        self.btn_start.pack(side="left", padx=5)

        self.btn_stop = ctk.CTkButton(
            btn_container, 
            text="중단", 
            width=60, 
            fg_color="#a83232", 
            hover_color="#702020",
            state="disabled", 
            command=self._stop_scan
        )
        self.btn_stop.pack(side="left")

        # 4. 결과 테이블, 통계 및 툴바
        result_frame = ctk.CTkFrame(self, corner_radius=10)
        result_frame.grid(row=4, column=0, padx=15, pady=(0, 15), sticky="nsew")
        result_frame.grid_columnconfigure(0, weight=1)
        result_frame.grid_rowconfigure(3, weight=1)

        self.progress_bar = ctk.CTkProgressBar(result_frame)
        self.progress_bar.grid(row=0, column=0, padx=15, pady=(10, 4), sticky="ew")
        self.progress_bar.set(0)

        self.lbl_status = ctk.CTkLabel(result_frame, text="검사할 폴더를 지정한 후 [동기화 검사 시작]을 눌러주세요.", text_color="gray")
        self.lbl_status.grid(row=1, column=0, padx=15, pady=(0, 6), sticky="w")

        # 통계 배지
        summary_container = ctk.CTkFrame(result_frame, fg_color="transparent")
        summary_container.grid(row=2, column=0, padx=15, pady=(0, 8), sticky="ew")

        self.badge_total = self._create_badge(summary_container, "전체: 0", "#4A5568")
        self.badge_synced = self._create_badge(summary_container, "정상 동기화: 0", "#2E7D32")
        self.badge_missing = self._create_badge(summary_container, "웹 업로드 누락: 0", "#C62828")
        self.badge_mismatch = self._create_badge(summary_container, "불일치: 0", "#EF6C00")
        self.badge_extra = self._create_badge(summary_container, "웹 전용: 0", "#1565C0")

        # 툴바: 필터, 검색, CSV 내보내기
        toolbar = ctk.CTkFrame(result_frame, fg_color="transparent")
        toolbar.grid(row=3, column=0, padx=15, pady=(0, 8), sticky="ew")
        toolbar.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(toolbar, text="보기 필터:").grid(row=0, column=0, padx=(0, 6), sticky="w")
        self.filter_combobox = ctk.CTkComboBox(
            toolbar, 
            values=["⚠️ 문제 항목만 (누락 + 불일치)", "모든 파일 보기", "🔴 웹 업로드 누락만", "🟡 불일치 파일만", "🟢 동기화 완료만"],
            width=230,
            command=self._apply_filter
        )
        self.filter_combobox.set("⚠️ 문제 항목만 (누락 + 불일치)")
        self.filter_combobox.grid(row=0, column=1, padx=(0, 15), sticky="w")

        self.search_entry = ctk.CTkEntry(toolbar, placeholder_text="파일명 검색...", width=180)
        self.search_entry.grid(row=0, column=2, padx=(0, 10), sticky="w")
        self.search_entry.bind("<KeyRelease>", lambda e: self._apply_filter())

        btn_action_container = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_action_container.grid(row=0, column=3, sticky="e")

        btn_export = ctk.CTkButton(
            btn_action_container,
            text="📥 CSV 리포트 내보내기",
            width=140,
            command=self._export_csv
        )
        btn_export.pack(side="left")

        # 결과 테이블
        table_container = ctk.CTkFrame(result_frame, fg_color="transparent")
        table_container.grid(row=4, column=0, padx=15, pady=(0, 12), sticky="nsew")
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        columns = ("status", "rel_path", "local_size", "gdrive_size", "local_mtime", "gdrive_mtime", "detail")
        self.tree = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="extended")

        self.tree.heading("status", text="동기화 상태")
        self.tree.heading("rel_path", text="상대 파일 경로")
        self.tree.heading("local_size", text="PC 크기")
        self.tree.heading("gdrive_size", text="웹 클라우드 크기")
        self.tree.heading("local_mtime", text="PC 수정시각")
        self.tree.heading("gdrive_mtime", text="웹 클라우드 수정시각")
        self.tree.heading("detail", text="상세 정보")

        self.tree.column("status", width=125, anchor="center")
        self.tree.column("rel_path", width=340, anchor="w")
        self.tree.column("local_size", width=85, anchor="e")
        self.tree.column("gdrive_size", width=95, anchor="e")
        self.tree.column("local_mtime", width=135, anchor="center")
        self.tree.column("gdrive_mtime", width=135, anchor="center")
        self.tree.column("detail", width=220, anchor="w")

        self.tree.tag_configure("tag_missing", foreground="#C62828")
        self.tree.tag_configure("tag_mismatch", foreground="#D84315")
        self.tree.tag_configure("tag_synced", foreground="#2E7D32")
        self.tree.tag_configure("tag_extra", foreground="#1565C0")

        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

    def _create_badge(self, parent, text, color):
        lbl = ctk.CTkLabel(
            parent, text=text, fg_color=color, text_color="white", corner_radius=6, padx=9, pady=3,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl.pack(side="left", padx=4)
        return lbl

    def _load_auto_detected_pairs(self):
        """PC에 설정된 Google Drive 동기화 폴더 자동 감지"""
        self.detected_pairs = detect_sync_pairs()
        if self.detected_pairs:
            display_list = [p[0] for p in self.detected_pairs]
            self.detected_combobox.configure(values=display_list)
            self.detected_combobox.set(display_list[0])
            self._on_detected_pair_selected(display_list[0])
        else:
            self.detected_combobox.configure(values=["감지된 동기화 폴더 없음"])
            self.detected_combobox.set("감지된 동기화 폴더 없음")

    def _on_detected_pair_selected(self, choice):
        for name, local, gdrive in self.detected_pairs:
            if name == choice:
                # 단일 폴더 모드일 때는 gdrive 경로 설정
                if gdrive:
                    self.single_path_entry.delete(0, "end")
                    self.single_path_entry.insert(0, gdrive)
                # 2개 폴더 모드용 필드도 업데이트
                if local:
                    self.local_path_entry.delete(0, "end")
                    self.local_path_entry.insert(0, local)
                if gdrive:
                    self.gdrive_path_entry.delete(0, "end")
                    self.gdrive_path_entry.insert(0, gdrive)
                break

    def _on_mode_change(self, value):
        is_web_sync_mode = "웹 동기화 검사" in value

        if is_web_sync_mode:
            # 1번 모드: 단일 폴더 모드 (PC G: 드라이브 ↔ 웹 서버 직접 대조)
            self.lbl_local_path.grid_remove()
            self.local_path_entry.grid_remove()
            self.btn_browse_local.grid_remove()
            self.lbl_gdrive_target.grid_remove()
            self.gdrive_path_entry.grid_remove()
            self.btn_browse_gdrive.grid_remove()

            self.lbl_single_path.grid(row=0, column=0, padx=15, pady=(12, 6), sticky="w")
            self.single_path_entry.grid(row=0, column=1, padx=(0, 10), pady=(12, 6), sticky="ew")
            self.btn_browse_single.grid(row=0, column=2, padx=(0, 15), pady=(12, 6))
            self.api_status_frame.grid(row=1, column=0, columnspan=3, padx=15, pady=(4, 10), sticky="ew")

            self.badge_missing.configure(text="웹 업로드 누락: 0")
            self.badge_extra.configure(text="웹 전용: 0")
            self.tree.heading("local_size", text="PC 크기")
            self.tree.heading("gdrive_size", text="웹 클라우드 크기")
            self.tree.heading("local_mtime", text="PC 수정시각")
            self.tree.heading("gdrive_mtime", text="웹 클라우드 수정시각")
        else:
            # 2번 모드: 로컬 C:\ ↔ Google Drive 폴더 비교
            self.lbl_single_path.grid_remove()
            self.single_path_entry.grid_remove()
            self.btn_browse_single.grid_remove()
            self.api_status_frame.grid_remove()

            self.lbl_local_path.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="w")
            self.local_path_entry.grid(row=0, column=1, padx=(0, 10), pady=(10, 5), sticky="ew")
            self.btn_browse_local.grid(row=0, column=2, padx=(0, 15), pady=(10, 5))

            self.lbl_gdrive_target.grid(row=1, column=0, padx=15, pady=(5, 10), sticky="w")
            self.gdrive_path_entry.grid(row=1, column=1, padx=(0, 10), pady=(5, 10), sticky="ew")
            self.btn_browse_gdrive.grid(row=1, column=2, padx=(0, 15), pady=(5, 10))

            self.badge_missing.configure(text="드라이브 누락: 0")
            self.badge_extra.configure(text="드라이브 전용: 0")
            self.tree.heading("local_size", text="로컬 크기")
            self.tree.heading("gdrive_size", text="드라이브 크기")
            self.tree.heading("local_mtime", text="로컬 수정시각")
            self.tree.heading("gdrive_mtime", text="드라이브 수정시각")

    def _check_existing_api_token(self):
        if os.path.exists("token.json"):
            try:
                user = self.api_client.authenticate()
                email = user.get("emailAddress", "")
                name = user.get("displayName", "")
                self.lbl_api_auth.configure(
                    text=f"API 인증 완료: {name} ({email})" if email else f"API 인증 완료: {name}",
                    text_color="#2E7D32"
                )
            except Exception:
                self.lbl_api_auth.configure(text="API 인증 만료 (재인증 필요)", text_color="#D84315")
        else:
            self.lbl_api_auth.configure(text="API 미인증 (Google 로그인 필요)", text_color="#D84315")

    def _authenticate_api(self):
        cred_file = "credentials.json"
        if not os.path.exists(cred_file):
            cred_file = filedialog.askopenfilename(
                title="Google Cloud OAuth credentials.json 파일 선택",
                filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
            )
            if not cred_file:
                return

        def run_auth():
            try:
                user = self.api_client.authenticate(cred_file)
                email = user.get("emailAddress", "")
                name = user.get("displayName", "")
                self.after(0, lambda: self.lbl_api_auth.configure(
                    text=f"API 인증 완료: {name} ({email})",
                    text_color="#2E7D32"
                ))
                self.after(0, lambda: messagebox.showinfo("인증 성공", f"Google Drive API 인증에 성공했습니다!\n사용자: {name} ({email})"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("인증 실패", f"API 인증 중 오류가 발생했습니다:\n{str(e)}"))

        threading.Thread(target=run_auth, daemon=True).start()

    def _browse_single(self):
        initial = r"G:\다른 컴퓨터\내 컴퓨터" if os.path.exists(r"G:\다른 컴퓨터\내 컴퓨터") else "G:\\"
        folder = filedialog.askdirectory(title="검사할 PC의 Google Drive 폴더 선택", initialdir=initial)
        if folder:
            self.single_path_entry.delete(0, "end")
            self.single_path_entry.insert(0, os.path.normpath(folder))

    def _browse_local(self):
        folder = filedialog.askdirectory(title="로컬 원본 폴더 선택")
        if folder:
            self.local_path_entry.delete(0, "end")
            self.local_path_entry.insert(0, os.path.normpath(folder))

    def _browse_gdrive(self):
        initial = r"G:\다른 컴퓨터\내 컴퓨터" if os.path.exists(r"G:\다른 컴퓨터\내 컴퓨터") else "G:\\"
        folder = filedialog.askdirectory(title="Google Drive 대상 폴더 선택", initialdir=initial)
        if folder:
            self.gdrive_path_entry.delete(0, "end")
            self.gdrive_path_entry.insert(0, os.path.normpath(folder))

    def _start_scan(self):
        mode = self.mode_segment.get()
        is_web_sync_mode = "웹 동기화 검사" in mode

        if is_web_sync_mode:
            target_path = self.single_path_entry.get().strip()
            if not target_path or not os.path.isdir(target_path):
                messagebox.showerror("오류", "유효한 PC의 Google Drive 폴더를 지정해주세요.")
                return

            if not self.api_client.is_authenticated():
                try:
                    self.api_client.authenticate()
                except Exception as e:
                    messagebox.showerror("인증 필요", f"Google Drive API 인증이 필요합니다:\n{str(e)}")
                    return
        else:
            local_dir = self.local_path_entry.get().strip()
            gdrive_target = self.gdrive_path_entry.get().strip()
            if not local_dir or not os.path.isdir(local_dir):
                messagebox.showerror("오류", "유효한 로컬 폴더를 지정해주세요.")
                return
            if not gdrive_target or not os.path.isdir(gdrive_target):
                messagebox.showerror("오류", "유효한 Google Drive 폴더를 지정해주세요.")
                return

        # UI 비활성화
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.progress_bar.set(0)
        self.lbl_status.configure(text="검사를 시작합니다...", text_color="black")

        self.all_results = []
        for item in self.tree.get_children():
            self.tree.delete(item)

        def progress(current, total, msg):
            def update():
                if total > 0:
                    self.progress_bar.set(current / total)
                self.lbl_status.configure(text=msg)
            self.after(0, update)

        def run():
            try:
                if is_web_sync_mode:
                    folder_name = os.path.basename(os.path.normpath(target_path))
                    self.lbl_status.configure(text=f"Google Drive 웹에서 '{folder_name}' 폴더를 찾는 중...")
                    folder_id = self.api_client.resolve_folder_id(target_path, default_name=folder_name)
                    
                    results = self.api_client.compare_with_local(
                        local_dir=target_path,
                        root_folder_id=folder_id,
                        check_hash=self.hash_check_var.get(),
                        exclude_system=self.exclude_system_var.get(),
                        progress_callback=progress
                    )
                else:
                    self.comparator = SyncComparator(
                        local_dir=local_dir,
                        gdrive_dir=gdrive_target,
                        check_hash=self.hash_check_var.get(),
                        exclude_system=self.exclude_system_var.get()
                    )
                    results = self.comparator.compare(progress_callback=progress)

                self.after(0, lambda: self._on_scan_finished(results))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("검사 오류", f"검사 중 오류가 발생했습니다:\n{str(e)}"))
                self.after(0, self._reset_controls)

        self.scan_thread = threading.Thread(target=run, daemon=True)
        self.scan_thread.start()

    def _stop_scan(self):
        if self.comparator:
            self.comparator.cancel()
        if self.api_client:
            self.api_client.cancel()
        self.lbl_status.configure(text="검사 중단 중...", text_color="orange")

    def _reset_controls(self):
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    def _on_scan_finished(self, results: list[FileItem]):
        self._reset_controls()
        self.all_results = results
        self.progress_bar.set(1.0)
        self.lbl_status.configure(text=f"검사 완료! (총 {len(results)}개 파일 대조 완료)", text_color="#2E7D32")

        mode = self.mode_segment.get()
        is_web_sync_mode = "웹 동기화 검사" in mode

        total_count = len(results)
        synced_count = sum(1 for r in results if r.status == SyncStatus.SYNCED)
        missing_count = sum(1 for r in results if r.status == SyncStatus.MISSING_IN_GDRIVE)
        mismatch_count = sum(1 for r in results if r.status in (SyncStatus.SIZE_MISMATCH, SyncStatus.TIME_MISMATCH, SyncStatus.HASH_MISMATCH))
        extra_count = sum(1 for r in results if r.status == SyncStatus.EXTRA_IN_GDRIVE)

        self.badge_total.configure(text=f"전체: {total_count}")
        self.badge_synced.configure(text=f"정상 동기화: {synced_count}")
        
        if is_web_sync_mode:
            self.badge_missing.configure(text=f"웹 업로드 누락: {missing_count}")
            self.badge_extra.configure(text=f"웹 전용: {extra_count}")
        else:
            self.badge_missing.configure(text=f"드라이브 누락: {missing_count}")
            self.badge_extra.configure(text=f"드라이브 전용: {extra_count}")

        self.badge_mismatch.configure(text=f"불일치: {mismatch_count}")

        self._apply_filter()

    def _apply_filter(self, choice=None):
        filter_mode = self.filter_combobox.get()
        query = self.search_entry.get().strip().lower()

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.filtered_results = []
        for r in self.all_results:
            if query and query not in r.rel_path.lower():
                continue

            if "문제 항목만" in filter_mode and not r.is_problematic:
                continue
            elif ("누락만" in filter_mode) and r.status != SyncStatus.MISSING_IN_GDRIVE:
                continue
            elif "불일치 파일만" in filter_mode and r.status not in (SyncStatus.SIZE_MISMATCH, SyncStatus.TIME_MISMATCH, SyncStatus.HASH_MISMATCH):
                continue
            elif "동기화 완료만" in filter_mode and r.status != SyncStatus.SYNCED:
                continue

            self.filtered_results.append(r)

            if r.status == SyncStatus.MISSING_IN_GDRIVE:
                tag = "tag_missing"
            elif r.is_problematic:
                tag = "tag_mismatch"
            elif r.status == SyncStatus.SYNCED:
                tag = "tag_synced"
            else:
                tag = "tag_extra"

            self.tree.insert("", "end", values=(
                r.status.value,
                r.rel_path,
                format_size(r.local_size),
                format_size(r.gdrive_size),
                format_time(r.local_mtime),
                format_time(r.gdrive_mtime),
                r.detail
            ), tags=(tag,))

    def _export_csv(self):
        if not self.all_results:
            messagebox.showinfo("알림", "내보낼 검사 결과가 없습니다.")
            return

        filepath = filedialog.asksaveasfilename(
            title="CSV 리포트 저장",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not filepath:
            return

        try:
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["상태", "상대경로", "PC크기(Byte)", "웹크기(Byte)", "PC수정일시", "웹수정일시", "상세정보"])
                for r in self.all_results:
                    writer.writerow([
                        r.status.value,
                        r.rel_path,
                        r.local_size if r.local_size >= 0 else "",
                        r.gdrive_size if r.gdrive_size >= 0 else "",
                        format_time(r.local_mtime),
                        format_time(r.gdrive_mtime),
                        r.detail
                    ])
            messagebox.showinfo("완료", f"CSV 리포트가 성공적으로 저장되었습니다:\n{filepath}")
        except Exception as e:
            messagebox.showerror("저장 실패", f"CSV 저장 중 오류 발생:\n{str(e)}")
