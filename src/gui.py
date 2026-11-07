import os
import csv
import threading
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk

from src.comparator import SyncComparator, SyncStatus, FileItem
from src.utils import format_size, format_time

ctk.set_appearance_mode("System")  # 시스템 테마(Dark/Light) 자동 연동
ctk.set_default_color_theme("blue")

class SyncCheckerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Google Drive 동기화 상태 검사기 (Sync Checker)")
        self.geometry("1100 biographicalx750".replace("biographical", "")) # 1100x750
        self.minsize(950, 650)

        # 상태 변수
        self.comparator = None
        self.scan_thread = None
        self.all_results: list[FileItem] = []
        self.filtered_results: list[FileItem] = []

        self._build_ui()
        self._set_default_gdrive_path()

    def _set_default_gdrive_path(self):
        """G:\내 드라이브 가 기본적으로 존재하면 자동 채우기"""
        candidates = [
            r"G:\내 드라이브",
            r"G:\My Drive",
            r"G:\"
        ]
        for path in candidates:
            if os.path.exists(path):
                self.gdrive_path_entry.delete(0, "end")
                self.gdrive_path_entry.insert(0, path)
                break

    def _build_ui(self):
        # 최상단 메인 컨테이너
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # 1. 헤더 & 경로 선택 프레임
        input_frame = ctk.CTkFrame(self, corner_radius=10)
        input_frame.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="ew")
        input_frame.grid_columnconfigure(1, weight=1)

        # 로컬 폴더
        ctk.CTkLabel(input_frame, text="로컬 원본 폴더:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=15, pady=(12, 6), sticky="w"
        )
        self.local_path_entry = ctk.CTkEntry(input_frame, placeholder_text="검사할 PC의 로컬 폴더 경로를 선택하세요 (예: C:\\Users\\...\\Documents)")
        self.local_path_entry.grid(row=0, column=1, padx=(0, 10), pady=(12, 6), sticky="ew")
        
        btn_browse_local = ctk.CTkButton(input_frame, text="폴더 선택", width=90, command=self._browse_local)
        btn_browse_local.grid(row=0, column=2, padx=(0, 15), pady=(12, 6))

        # Google Drive 폴더
        ctk.CTkLabel(input_frame, text="Google Drive 폴더:", font=ctk.CTkFont(weight="bold")).grid(
            row=1, column=0, padx=15, pady=(6, 12), sticky="w"
        )
        self.gdrive_path_entry = ctk.CTkEntry(input_frame, placeholder_text="비교할 Google Drive 대상 폴더 (예: G:\\내 드라이브\\...)")
        self.gdrive_path_entry.grid(row=1, column=1, padx=(0, 10), pady=(6, 12), sticky="ew")

        btn_browse_gdrive = ctk.CTkButton(input_frame, text="드라이브 선택", width=90, command=self._browse_gdrive)
        btn_browse_gdrive.grid(row=1, column=2, padx=(0, 15), pady=(6, 12))

        # 2. 검사 옵션 및 컨트롤 버튼 프레임
        control_frame = ctk.CTkFrame(self, corner_radius=10)
        control_frame.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="ew")
        control_frame.grid_columnconfigure(2, weight=1)

        self.hash_check_var = ctk.BooleanVar(value=False)
        self.hash_checkbox = ctk.CTkCheckBox(
            control_frame, 
            text="정밀 검사 (MD5 해시 대조 - 대용량 파일은 시간이 조금 더 걸림)", 
            variable=self.hash_check_var
        )
        self.hash_checkbox.grid(row=0, column=0, padx=15, pady=10, sticky="w")

        self.exclude_system_var = ctk.BooleanVar(value=True)
        self.exclude_checkbox = ctk.CTkCheckBox(
            control_frame, 
            text="시스템/임시 파일 제외 (.git, desktop.ini 등)", 
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

        # 3. 진행 상황 및 상태 카드 요약
        status_frame = ctk.CTkFrame(self, corner_radius=10)
        status_frame.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="ew")
        status_frame.grid_columnconfigure(0, weight=1)

        # 프로그레스 바 및 텍스트
        self.progress_bar = ctk.CTkProgressBar(status_frame)
        self.progress_bar.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="ew")
        self.progress_bar.set(0)

        self.lbl_status = ctk.CTkLabel(status_frame, text="검사할 폴더를 지정한 후 [동기화 검사 시작]을 눌러주세요.", text_color="gray")
        self.lbl_status.grid(row=1, column=0, padx=15, pady=(0, 8), sticky="w")

        # 통계 배지
        summary_container = ctk.CTkFrame(status_frame, fg_color="transparent")
        summary_container.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="ew")

        self.badge_total = self._create_badge(summary_container, "전체: 0", "#4A5568")
        self.badge_synced = self._create_badge(summary_container, "정상 동기화: 0", "#2E7D32")
        self.badge_missing = self._create_badge(summary_container, "드라이브 누락: 0", "#C62828")
        self.badge_mismatch = self._create_badge(summary_container, "불일치: 0", "#EF6C00")
        self.badge_extra = self._create_badge(summary_container, "드라이브 전용: 0", "#1565C0")

        # 4. 결과 테이블 및 필터/액션 툴바
        result_frame = ctk.CTkFrame(self, corner_radius=10)
        result_frame.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="nsew")
        result_frame.grid_columnconfigure(0, weight=1)
        result_frame.grid_rowconfigure(1, weight=1)

        # 툴바: 필터, 검색, 원클릭 동기화 복사, 내보내기
        toolbar = ctk.CTkFrame(result_frame, fg_color="transparent")
        toolbar.grid(row=0, column=0, padx=15, pady=(10, 8), sticky="ew")
        toolbar.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(toolbar, text="보기 필터:").grid(row=0, column=0, padx=(0, 8), sticky="w")
        self.filter_combobox = ctk.CTkComboBox(
            toolbar, 
            values=["모든 파일 보기", "⚠️ 문제 항목만 (누락 + 불일치)", "🔴 구글드라이브 누락만", "🟡 불일치 파일만", "🟢 동기화 완료만"],
            width=230,
            command=self._apply_filter
        )
        self.filter_combobox.set("⚠️ 문제 항목만 (누락 + 불일치)")
        self.filter_combobox.grid(row=0, column=1, padx=(0, 15), sticky="w")

        # 검색창
        self.search_entry = ctk.CTkEntry(toolbar, placeholder_text="파일명 검색...", width=200)
        self.search_entry.grid(row=0, column=2, padx=(0, 15), sticky="w")
        self.search_entry.bind("<KeyRelease>", lambda e: self._apply_filter())

        # 동기화 조치 버튼 & CSV 내보내기
        btn_action_container = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_action_container.grid(row=0, column=3, sticky="e")

        self.btn_sync_now = ctk.CTkButton(
            btn_action_container,
            text="🚀 누락/불일치 파일 Drive로 즉시 복사",
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            command=self._sync_selected_files
        )
        self.btn_sync_now.pack(side="left", padx=5)

        btn_export = ctk.CTkButton(
            btn_action_container,
            text="📥 CSV 내보내기",
            width=100,
            command=self._export_csv
        )
        btn_export.pack(side="left")

        # 테이블 (ttk.Treeview 사용으로 대량의 데이터도 초고속 렌더링)
        table_container = ctk.CTkFrame(result_frame, fg_color="transparent")
        table_container.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        columns = ("status", "rel_path", "local_size", "gdrive_size", "local_mtime", "gdrive_mtime", "detail")
        self.tree = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="extended")

        self.tree.heading("status", text="동기화 상태")
        self.tree.heading("rel_path", text="상대 파일 경로")
        self.tree.heading("local_size", text="로컬 크기")
        self.tree.heading("gdrive_size", text="드라이브 크기")
        self.tree.heading("local_mtime", text="로컬 수정시각")
        self.tree.heading("gdrive_mtime", text="드라이브 수정시각")
        self.tree.heading("detail", text="상세 정보")

        self.tree.column("status", width=130, anchor="center")
        self.tree.column("rel_path", width=330, anchor="w")
        self.tree.column("local_size", width=90, anchor="e")
        self.tree.column("gdrive_size", width=90, anchor="e")
        self.tree.column("local_mtime", width=140, anchor="center")
        self.tree.column("gdrive_mtime", width=140, anchor="center")
        self.tree.column("detail", width=200, anchor="w")

        # 태그 스타일 설정 (색상 강조)
        self.tree.tag_configure("tag_missing", foreground="#C62828")
        self.tree.tag_configure("tag_mismatch", foreground="#D84315")
        self.tree.tag_configure("tag_synced", foreground="#2E7D32")
        self.tree.tag_configure("tag_extra", foreground="#1565C0")

        # 스크롤바 연결
        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

    def _create_badge(self, parent, text, color):
        lbl = ctk.CTkLabel(
            parent, 
            text=text, 
            fg_color=color, 
            text_color="white", 
            corner_radius=6, 
            padx=10, 
            pady=4,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl.pack(side="left", padx=5)
        return lbl

    def _browse_local(self):
        folder = filedialog.askdirectory(title="로컬 원본 폴더 선택")
        if folder:
            self.local_path_entry.delete(0, "end")
            self.local_path_entry.insert(0, os.path.normpath(folder))

    def _browse_gdrive(self):
        initial = r"G:\내 드라이브" if os.path.exists(r"G:\내 드라이브") else "G:\\"
        folder = filedialog.askdirectory(title="Google Drive 대상 폴더 선택", initialdir=initial)
        if folder:
            self.gdrive_path_entry.delete(0, "end")
            self.gdrive_path_entry.insert(0, os.path.normpath(folder))

    def _start_scan(self):
        local_dir = self.local_path_entry.get().strip()
        gdrive_dir = self.gdrive_path_entry.get().strip()

        if not local_dir or not os.path.isdir(local_dir):
            messagebox.showerror("오류", "유효한 로컬 폴더를 지정해주세요.")
            return
        if not gdrive_dir or not os.path.isdir(gdrive_dir):
            messagebox.showerror("오류", "유효한 Google Drive 폴더를 지정해주세요.")
            return

        # UI 비활성화/활성화 전환
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.progress_bar.set(0)
        self.lbl_status.configure(text="스캔 및 검사를 시작합니다...", text_color="black")
        
        # 이전 결과 초기화
        self.all_results = []
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.comparator = SyncComparator(
            local_dir=local_dir,
            gdrive_dir=gdrive_dir,
            check_hash=self.hash_check_var.get(),
            exclude_system=self.exclude_system_var.get()
        )

        def run():
            def progress(current, total, msg):
                def update():
                    if total > 0:
                        self.progress_bar.set(current / total)
                    self.lbl_status.configure(text=msg)
                self.after(0, update)

            try:
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
            self.lbl_status.configure(text="검사 중단 중...", text_color="orange")

    def _reset_controls(self):
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")

    def _on_scan_finished(self, results: list[FileItem]):
        self._reset_controls()
        self.all_results = results
        self.progress_bar.set(1.0)
        self.lbl_status.configure(text=f"검사 완료! (총 {len(results)}개 파일 대조 완료)", text_color="#2E7D32")

        # 통계 계산
        total_count = len(results)
        synced_count = sum(1 for r in results if r.status == SyncStatus.SYNCED)
        missing_count = sum(1 for r in results if r.status == SyncStatus.MISSING_IN_GDRIVE)
        mismatch_count = sum(1 for r in results if r.status in (SyncStatus.SIZE_MISMATCH, SyncStatus.TIME_MISMATCH, SyncStatus.HASH_MISMATCH))
        extra_count = sum(1 for r in results if r.status == SyncStatus.EXTRA_IN_GDRIVE)

        self.badge_total.configure(text=f"전체: {total_count}")
        self.badge_synced.configure(text=f"정상 동기화: {synced_count}")
        self.badge_missing.configure(text=f"드라이브 누락: {missing_count}")
        self.badge_mismatch.configure(text=f"불일치: {mismatch_count}")
        self.badge_extra.configure(text=f"드라이브 전용: {extra_count}")

        # 필터 적용
        self._apply_filter()

    def _apply_filter(self, choice=None):
        filter_mode = self.filter_combobox.get()
        query = self.search_entry.get().strip().lower()

        # 기존 테이블 비우기
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.filtered_results = []
        for r in self.all_results:
            # 검색어 필터
            if query and query not in r.rel_path.lower():
                continue

            # 상태 필터
            if "문제 항목만" in filter_mode and not r.is_problematic:
                continue
            elif "구글드라이브 누락만" in filter_mode and r.status != SyncStatus.MISSING_IN_GDRIVE:
                continue
            elif "불일치 파일만" in filter_mode and r.status not in (SyncStatus.SIZE_MISMATCH, SyncStatus.TIME_MISMATCH, SyncStatus.HASH_MISMATCH):
                continue
            elif "동기화 완료만" in filter_mode and r.status != SyncStatus.SYNCED:
                continue

            self.filtered_results.append(r)

            # 태그 결정
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

    def _sync_selected_files(self):
        """누락되거나 불일치하는 로컬 파일들을 Google Drive로 복사"""
        problem_items = [r for r in self.all_results if r.is_problematic and r.local_size >= 0]
        if not problem_items:
            messagebox.showinfo("알림", "Google Drive로 복사할 미동기화/불일치 파일이 없습니다.")
            return

        msg = (
            f"발견된 {len(problem_items)}개의 미동기화/불일치 파일을 Google Drive 대상 폴더로 지금 복사하시겠습니까?\n\n"
            f"대상 경로: {self.gdrive_path_entry.get()}\n"
            f"※ 복사 시 Google Drive 데스크톱 앱이 변경을 감지하고 클라우드로 자동 업로드하게 됩니다."
        )
        if not messagebox.askyesno("동기화 복사 확인", msg):
            return

        self.btn_sync_now.configure(state="disabled")
        self.btn_start.configure(state="disabled")

        def run_copy():
            def progress(curr, tot, text):
                self.after(0, lambda: self.lbl_status.configure(text=text))
                self.after(0, lambda: self.progress_bar.set(curr / tot))

            copied = self.comparator.sync_to_gdrive(problem_items, progress_callback=progress)
            self.after(0, lambda: messagebox.showinfo("동기화 완료", f"총 {copied}개 파일이 Google Drive로 복사되었습니다.\n검사를 다시 실행합니다."))
            self.after(0, self._start_scan)

        threading.Thread(target=run_copy, daemon=True).start()

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
                writer.writerow(["상태", "상대경로", "로컬크기(Byte)", "드라이브크기(Byte)", "로컬수정일시", "드라이브수정일시", "상세정보"])
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
