"""
Main Window
PySide6 main application window with drag-drop support
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTableWidget, QTableWidgetItem,
    QStatusBar, QToolBar, QFileDialog, QMessageBox, QSpinBox,
    QGroupBox, QHeaderView, QSplitter, QTextEdit, QFrame, QListWidget,
    QListWidgetItem, QAbstractItemView
)
from PySide6.QtCore import Qt, QTimer, Slot, QMimeData
from PySide6.QtGui import QAction, QIcon, QColor, QDragEnterEvent, QDropEvent
from loguru import logger

from app.config import config
from app.core.orchestrator import Orchestrator
from app.core.scanner import FolderScanner
from app.services.youtube_api import youtube_api


class DropZone(QFrame):
    """
    Drag-drop zone for folders
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setMinimumHeight(80)
        self.setStyleSheet("""
            DropZone {
                background-color: #f0f0f0;
                border: 2px dashed #aaa;
                border-radius: 8px;
            }
            DropZone:hover {
                background-color: #e8f5e9;
                border-color: #4CAF50;
            }
        """)
        
        layout = QVBoxLayout(self)
        self.label = QLabel("📂 ลาก Folder มาวางที่นี่\nหรือคลิก 'Add Folder'")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.label)
        
        # Callback for when folders are dropped
        self.on_folders_dropped = None
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                DropZone {
                    background-color: #c8e6c9;
                    border: 2px solid #4CAF50;
                    border-radius: 8px;
                }
            """)
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            DropZone {
                background-color: #f0f0f0;
                border: 2px dashed #aaa;
                border-radius: 8px;
            }
        """)
    
    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("""
            DropZone {
                background-color: #f0f0f0;
                border: 2px dashed #aaa;
                border-radius: 8px;
            }
        """)
        
        folders = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).is_dir():
                folders.append(path)
        
        if folders and self.on_folders_dropped:
            self.on_folders_dropped(folders)


class MainWindow(QMainWindow):
    """
    Main application window
    Layout: Sidebar + Main content (task queue + progress)
    """
    
    def __init__(self):
        super().__init__()
        
        self._orchestrator = Orchestrator()
        self._selected_folders: list[str] = []
        self._scanned_data: dict = {}  # folder_path -> ScannedFolder
        
        self._setup_ui()
        self._connect_signals()
        self._load_state()
        
        logger.info("MainWindow initialized")
    
    def _setup_ui(self):
        """Setup UI components"""
        self.setWindowTitle("MTYoutubeAutoPost - YouTube Bulk Uploader")
        self.setMinimumSize(800, 600)  # Smaller minimum for flexibility
        
        # Allow free resizing
        self.setSizePolicy(
            self.sizePolicy().horizontalPolicy(),
            self.sizePolicy().verticalPolicy()
        )
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Left sidebar
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar, 1)
        
        # Right content area
        content = self._create_content_area()
        main_layout.addWidget(content, 3)
        
        # Status bar
        self._create_status_bar()
        
        # Toolbar
        self._create_toolbar()
        
        # Restore window state
        self._restore_window_state()
    
    def _create_sidebar(self) -> QWidget:
        """Create left sidebar with controls"""
        sidebar = QWidget()
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # ====== Folder selection with drag-drop ======
        folder_group = QGroupBox("📁 Folders")
        folder_layout = QVBoxLayout(folder_group)
        
        # Drag-drop zone
        self.drop_zone = DropZone()
        self.drop_zone.on_folders_dropped = self._on_folders_dropped
        folder_layout.addWidget(self.drop_zone)
        
        # Buttons row
        btn_row = QHBoxLayout()
        self.btn_add_folder = QPushButton("➕ Add")
        self.btn_add_folder.clicked.connect(self._on_add_folder)
        btn_row.addWidget(self.btn_add_folder)
        
        self.btn_clear_folders = QPushButton("🗑️ Clear")
        self.btn_clear_folders.clicked.connect(self._on_clear_folders)
        btn_row.addWidget(self.btn_clear_folders)
        folder_layout.addLayout(btn_row)
        
        # Folder list
        self.folder_list = QListWidget()
        self.folder_list.setMaximumHeight(120)
        self.folder_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.folder_list.itemClicked.connect(self._on_folder_selected)
        folder_layout.addWidget(self.folder_list)
        
        self.lbl_folder_count = QLabel("0 folders selected")
        self.lbl_folder_count.setStyleSheet("color: #666; font-size: 11px;")
        folder_layout.addWidget(self.lbl_folder_count)
        
        layout.addWidget(folder_group)
        
        # ====== Settings ======
        settings_group = QGroupBox("⚙️ Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        # Worker count
        worker_layout = QHBoxLayout()
        worker_layout.addWidget(QLabel("Workers:"))
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, 5)
        self.spin_workers.setValue(config.worker_count)
        self.spin_workers.valueChanged.connect(self._on_worker_count_changed)
        worker_layout.addWidget(self.spin_workers)
        settings_layout.addLayout(worker_layout)
        
        # Delay from
        delay_from_layout = QHBoxLayout()
        delay_from_layout.addWidget(QLabel("Delay from (s):"))
        self.spin_delay_from = QSpinBox()
        self.spin_delay_from.setRange(0, 600)
        self.spin_delay_from.setValue(config.delay_range[0])
        self.spin_delay_from.valueChanged.connect(self._on_delay_changed)
        delay_from_layout.addWidget(self.spin_delay_from)
        settings_layout.addLayout(delay_from_layout)
        
        # Delay to
        delay_to_layout = QHBoxLayout()
        delay_to_layout.addWidget(QLabel("Delay to (s):"))
        self.spin_delay_to = QSpinBox()
        self.spin_delay_to.setRange(0, 600)
        self.spin_delay_to.setValue(config.delay_range[1])
        self.spin_delay_to.valueChanged.connect(self._on_delay_changed)
        delay_to_layout.addWidget(self.spin_delay_to)
        settings_layout.addLayout(delay_to_layout)
        
        # Skip duplicate check checkbox
        self.chk_skip_dup = QCheckBox("Skip Duplicate Check (save quota)")
        self.chk_skip_dup.setChecked(False)
        self.chk_skip_dup.stateChanged.connect(self._on_skip_dup_changed)
        settings_layout.addWidget(self.chk_skip_dup)
        
        layout.addWidget(settings_group)
        
        # ====== Control buttons ======
        control_group = QGroupBox("🎮 Control")
        control_layout = QVBoxLayout(control_group)
        
        self.btn_start = QPushButton("▶️ Start")
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_start.clicked.connect(self._on_start)
        control_layout.addWidget(self.btn_start)
        
        self.btn_pause = QPushButton("⏸️ Pause")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._on_pause)
        control_layout.addWidget(self.btn_pause)
        
        self.btn_stop = QPushButton("⏹️ Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("background-color: #f44336; color: white;")
        self.btn_stop.clicked.connect(self._on_stop)
        control_layout.addWidget(self.btn_stop)
        
        layout.addWidget(control_group)
        
        # ====== YouTube auth ======
        auth_group = QGroupBox("🔑 YouTube")
        auth_layout = QVBoxLayout(auth_group)
        
        self.lbl_auth_status = QLabel("❌ Not authenticated")
        auth_layout.addWidget(self.lbl_auth_status)
        
        # API Key status
        self.lbl_key_status = QLabel("🔑 Keys: 0/0")
        self.lbl_key_status.setStyleSheet("color: #666; font-size: 11px;")
        auth_layout.addWidget(self.lbl_key_status)
        
        self.btn_auth = QPushButton("🔓 Authenticate")
        self.btn_auth.clicked.connect(self._on_authenticate)
        auth_layout.addWidget(self.btn_auth)
        
        self.btn_sync = QPushButton("🔄 Sync Videos")
        self.btn_sync.clicked.connect(self._on_sync_videos)
        auth_layout.addWidget(self.btn_sync)
        
        # Update key status on init
        self._update_key_status()
        
        layout.addWidget(auth_group)
        
        layout.addStretch()
        
        return sidebar
    
    def _create_content_area(self) -> QWidget:
        """Create main content area with file list, task queue, and progress"""
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # ====== Selected folder files ======
        files_group = QGroupBox("📄 Files in Selected Folder")
        files_layout = QVBoxLayout(files_group)
        
        self.files_table = QTableWidget()
        self.files_table.setColumnCount(5)
        self.files_table.setHorizontalHeaderLabels([
            "Filename", "Episode", "Type", "Size", "Duration"
        ])
        self.files_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.files_table.setAlternatingRowColors(True)
        self.files_table.setMaximumHeight(150)
        files_layout.addWidget(self.files_table)
        
        # Folder info
        self.lbl_folder_info = QLabel("เลือก folder เพื่อดูรายการไฟล์")
        self.lbl_folder_info.setStyleSheet("color: #666;")
        files_layout.addWidget(self.lbl_folder_info)
        
        layout.addWidget(files_group)
        
        # ====== Overall progress ======
        progress_group = QGroupBox("📊 Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)
        
        # Stats row
        stats_layout = QHBoxLayout()
        self.lbl_total = QLabel("Total: 0")
        self.lbl_completed = QLabel("✅ Completed: 0")
        self.lbl_completed.setStyleSheet("color: green;")
        self.lbl_failed = QLabel("❌ Failed: 0")
        self.lbl_failed.setStyleSheet("color: red;")
        self.lbl_remaining = QLabel("⏳ Remaining: 0")
        stats_layout.addWidget(self.lbl_total)
        stats_layout.addWidget(self.lbl_completed)
        stats_layout.addWidget(self.lbl_failed)
        stats_layout.addWidget(self.lbl_remaining)
        stats_layout.addStretch()
        progress_layout.addLayout(stats_layout)
        
        layout.addWidget(progress_group)
        
        # ====== Task queue table ======
        queue_group = QGroupBox("📋 Task Queue")
        queue_layout = QVBoxLayout(queue_group)
        
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(6)
        self.task_table.setHorizontalHeaderLabels([
            "Prod Code", "Episode", "Filename", "Status", "Progress", "Action"
        ])
        self.task_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.task_table.setAlternatingRowColors(True)
        queue_layout.addWidget(self.task_table)
        
        layout.addWidget(queue_group, 2)
        
        # ====== Logs ======
        log_group = QGroupBox("📝 Logs")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group, 1)
        
        return content
    
    def _create_status_bar(self):
        """Create status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - ลาก folder มาวางหรือคลิก Add Folder")
    
    def _create_toolbar(self):
        """Create toolbar"""
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        # Add actions
        toolbar.addAction("📁 Add Folder", self._on_add_folder)
        toolbar.addSeparator()
        toolbar.addAction("▶️ Start", self._on_start)
        toolbar.addAction("⏸️ Pause", self._on_pause)
        toolbar.addAction("⏹️ Stop", self._on_stop)
    
    def _connect_signals(self):
        """Connect orchestrator signals"""
        self._orchestrator.started.connect(self._on_session_started)
        self._orchestrator.paused.connect(self._on_session_paused)
        self._orchestrator.resumed.connect(self._on_session_resumed)
        self._orchestrator.stopped.connect(self._on_session_stopped)
        self._orchestrator.completed.connect(self._on_session_completed)
        self._orchestrator.progress_updated.connect(self._on_progress_updated)
        self._orchestrator.task_status_changed.connect(self._on_task_status_changed)
    
    def _load_state(self):
        """Load saved state including folders and session"""
        # Restore selected folders from last session
        saved_folders = config.get_ui('selected_folders', [])
        if saved_folders:
            reply = QMessageBox.question(
                self,
                "Restore Folders",
                f"Found {len(saved_folders)} folder(s) from last session.\nDo you want to restore them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                for folder in saved_folders:
                    if Path(folder).exists():
                        self._add_folder(folder)
                self._log(f"Restored {len(self._selected_folders)} folders from last session")
        
        # Check for resumable session (incomplete uploads)
        session_id = self._orchestrator.check_resumable_session()
        if session_id:
            reply = QMessageBox.question(
                self,
                "Resume Upload Session",
                f"Found incomplete upload session.\nDo you want to resume uploading?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._orchestrator.resume_from_crash()
                self._update_task_table()
                self._log("Resumed incomplete upload session")
    
    def _restore_window_state(self):
        """Restore window size and position"""
        width = config.get_ui('window.width', 1200)
        height = config.get_ui('window.height', 800)
        self.resize(width, height)
        
        if config.get_ui('window.maximized', False):
            self.showMaximized()
    
    def _save_window_state(self):
        """Save window size, position, and selected folders"""
        config.set_ui('window.width', self.width())
        config.set_ui('window.height', self.height())
        config.set_ui('window.maximized', self.isMaximized())
        
        # Save selected folders for next session
        config.set_ui('selected_folders', self._selected_folders)
        self._log(f"Saved state: {len(self._selected_folders)} folders")
    
    # ========================================
    # SLOT HANDLERS
    # ========================================
    
    def _on_folders_dropped(self, folders: list[str]):
        """Handle folders dropped via drag-drop"""
        for folder in folders:
            if folder not in self._selected_folders:
                self._add_folder(folder)
        self._log(f"Dropped {len(folders)} folder(s)")
    
    def _add_folder(self, folder: str):
        """Add a folder and scan it"""
        if folder in self._selected_folders:
            return
        
        # Scan folder
        scanned = FolderScanner.scan_folder(folder)
        
        if scanned.is_valid:
            self._selected_folders.append(folder)
            self._scanned_data[folder] = scanned
            
            # Add to list with icon
            item = QListWidgetItem(f"✅ {scanned.folder_name} ({scanned.video_count} videos)")
            item.setData(Qt.ItemDataRole.UserRole, folder)
            self.folder_list.addItem(item)
            
            self._log(f"Added: {scanned.folder_name} - {scanned.video_count} videos, prod_code: {scanned.prod_code}")
        else:
            # Show error
            item = QListWidgetItem(f"❌ {Path(folder).name} (invalid)")
            item.setData(Qt.ItemDataRole.UserRole, folder)
            item.setForeground(QColor(200, 100, 100))
            self.folder_list.addItem(item)
            
            errors = ", ".join(scanned.validation_errors)
            self._log(f"Invalid folder: {Path(folder).name} - {errors}")
        
        self._update_folder_count()
        
        # Auto-save folders
        config.set_ui('selected_folders', self._selected_folders)
    
    @Slot()
    def _on_add_folder(self):
        """Handle add folder button"""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self._add_folder(folder)
    
    @Slot()
    def _on_clear_folders(self):
        """Clear all folders"""
        self._selected_folders.clear()
        self._scanned_data.clear()
        self.folder_list.clear()
        self.files_table.setRowCount(0)
        self.lbl_folder_info.setText("เลือก folder เพื่อดูรายการไฟล์")
        self._update_folder_count()
        self._log("Cleared all folders")
    
    @Slot(QListWidgetItem)
    def _on_folder_selected(self, item: QListWidgetItem):
        """Handle folder selection in list"""
        folder = item.data(Qt.ItemDataRole.UserRole)
        if folder in self._scanned_data:
            self._show_folder_files(self._scanned_data[folder])
    
    def _show_folder_files(self, scanned):
        """Show files from selected folder"""
        self.files_table.setRowCount(len(scanned.videos))
        
        for i, video in enumerate(scanned.videos):
            self.files_table.setItem(i, 0, QTableWidgetItem(video.filename))
            self.files_table.setItem(i, 1, QTableWidgetItem(f"ep.{video.episode}"))
            self.files_table.setItem(i, 2, QTableWidgetItem(video.video_type))
            
            # Format file size
            size_mb = video.file_size / (1024 * 1024)
            self.files_table.setItem(i, 3, QTableWidgetItem(f"{size_mb:.1f} MB"))
            
            # Duration
            if video.metadata and video.metadata.duration_seconds > 0:
                duration = video.metadata.duration_formatted
            else:
                duration = "--:--"
            self.files_table.setItem(i, 4, QTableWidgetItem(duration))
        
        # Update info label
        info = f"📁 {scanned.folder_name} | prod_code: {scanned.prod_code} | {scanned.video_count} videos"
        self.lbl_folder_info.setText(info)
    
    @Slot()
    def _on_start(self):
        """Start processing"""
        if not self._selected_folders:
            QMessageBox.warning(self, "Warning", "Please add folders first")
            return
        
        # Process folders
        tasks = self._orchestrator.process_folders(self._selected_folders)
        
        if not tasks:
            QMessageBox.warning(self, "Warning", "No valid tasks found")
            return
        
        # Update table
        self._update_task_table()
        
        # Start
        self._orchestrator.start()
    
    @Slot()
    def _on_pause(self):
        """Pause processing"""
        if self._orchestrator.is_paused:
            self._orchestrator.resume()
        else:
            self._orchestrator.pause()
    
    @Slot()
    def _on_stop(self):
        """Stop processing"""
        reply = QMessageBox.question(
            self,
            "Confirm Stop",
            "Are you sure you want to stop? You can resume later.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._orchestrator.stop()
    
    @Slot()
    def _on_authenticate(self):
        """Authenticate with YouTube"""
        self._log(f"Starting YouTube authentication with key: {youtube_api.current_key_name}")
        success = youtube_api.authenticate()
        if success:
            self.lbl_auth_status.setText(f"✅ {youtube_api.current_key_name}")
            self._log(f"YouTube authentication successful with key: {youtube_api.current_key_name}")
        else:
            self.lbl_auth_status.setText("❌ Authentication failed")
            self._log("YouTube authentication failed")
        self._update_key_status()
    
    @Slot()
    def _on_sync_videos(self):
        """Sync videos from YouTube"""
        from app.core.duplicate_checker import DuplicateChecker
        self._log("Syncing videos from YouTube...")
        count = DuplicateChecker.sync_channel_videos()
        self._log(f"Synced {count} videos")
    
    @Slot(int)
    def _on_worker_count_changed(self, value: int):
        """Handle worker count change"""
        config.worker_count = value
        self._orchestrator.set_worker_count(value)
        self._log(f"Worker count: {value}")
    
    @Slot()
    def _on_delay_changed(self):
        """Handle delay change"""
        from_ss = self.spin_delay_from.value()
        to_ss = self.spin_delay_to.value()
        if to_ss < from_ss:
            to_ss = from_ss
            self.spin_delay_to.setValue(to_ss)
        config.delay_range = (from_ss, to_ss)
        self._orchestrator.set_delay_range(from_ss, to_ss)
        self._log(f"Delay range: {from_ss}-{to_ss}s")
    
    @Slot(int)
    def _on_skip_dup_changed(self, state: int):
        """Handle skip duplicate check changed"""
        skip = state == 2  # Qt.Checked = 2
        self._orchestrator.set_skip_duplicate_check(skip)
        self._log(f"Skip duplicate check: {'ON' if skip else 'OFF'}")
    
    @Slot()
    def _on_session_started(self):
        """Handle session started"""
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.status_bar.showMessage("Processing...")
        self._log("Session started")
    
    @Slot()
    def _on_session_paused(self):
        """Handle session paused"""
        self.btn_pause.setText("▶️ Resume")
        self.status_bar.showMessage("Paused")
        self._log("Session paused")
    
    @Slot()
    def _on_session_resumed(self):
        """Handle session resumed"""
        self.btn_pause.setText("⏸️ Pause")
        self.status_bar.showMessage("Processing...")
        self._log("Session resumed")
    
    @Slot()
    def _on_session_stopped(self):
        """Handle session stopped"""
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_pause.setText("⏸️ Pause")
        self.status_bar.showMessage("Stopped")
        self._log("Session stopped")
    
    @Slot()
    def _on_session_completed(self):
        """Handle session completed"""
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.status_bar.showMessage("Completed!")
        self._log("All tasks completed!")
        QMessageBox.information(self, "Complete", "All tasks have been completed!")
    
    @Slot(int, int, int)
    def _on_progress_updated(self, total: int, completed: int, failed: int):
        """Handle progress update"""
        remaining = total - completed - failed
        
        if total > 0:
            percent = int((completed + failed) / total * 100)
            self.progress_bar.setValue(percent)
        
        self.lbl_total.setText(f"Total: {total}")
        self.lbl_completed.setText(f"✅ Completed: {completed}")
        self.lbl_failed.setText(f"❌ Failed: {failed}")
        self.lbl_remaining.setText(f"⏳ Remaining: {remaining}")
    
    @Slot(str, str)
    def _on_task_status_changed(self, task_id: str, status: str):
        """Handle task status change"""
        self._update_task_table()
    
    # ========================================
    # HELPER METHODS
    # ========================================
    
    def _update_folder_count(self):
        """Update folder count label"""
        count = len(self._selected_folders)
        self.lbl_folder_count.setText(f"{count} folder(s) selected")
    
    def _update_task_table(self):
        """Update task table with current tasks"""
        tasks = self._orchestrator._tasks
        self.task_table.setRowCount(len(tasks))
        
        for i, task in enumerate(tasks):
            self.task_table.setItem(i, 0, QTableWidgetItem(task.prod_code))
            self.task_table.setItem(i, 1, QTableWidgetItem(f"ep.{task.episode}"))
            self.task_table.setItem(i, 2, QTableWidgetItem(task.filename))
            
            # Status with color
            status_item = QTableWidgetItem(task.status)
            if task.status == 'completed':
                status_item.setBackground(QColor(200, 255, 200))
            elif task.status == 'failed':
                status_item.setBackground(QColor(255, 200, 200))
            elif task.status == 'uploading':
                status_item.setBackground(QColor(255, 255, 200))
            self.task_table.setItem(i, 3, status_item)
            
            self.task_table.setItem(i, 4, QTableWidgetItem(f"{task.progress:.1f}%"))
            self.task_table.setItem(i, 5, QTableWidgetItem(task.action))
    
    def _update_key_status(self):
        """Update API key status display"""
        from app.services.api_key_manager import api_key_manager
        status = api_key_manager.get_status()
        total = status['total_keys']
        available = status['available_keys']
        current = status['current_name']
        
        if total > 0:
            self.lbl_key_status.setText(f"🔑 Keys: {available}/{total} ({current})")
            if available == 0:
                self.lbl_key_status.setStyleSheet("color: #f44336; font-size: 11px;")  # Red
            elif available < total:
                self.lbl_key_status.setStyleSheet("color: #ff9800; font-size: 11px;")  # Orange
            else:
                self.lbl_key_status.setStyleSheet("color: #4CAF50; font-size: 11px;")  # Green
        else:
            self.lbl_key_status.setText("🔑 No keys found")
            self.lbl_key_status.setStyleSheet("color: #f44336; font-size: 11px;")
    
    def _log(self, message: str):
        """Add log message"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def closeEvent(self, event):
        """Handle window close"""
        self._save_window_state()
        
        if self._orchestrator.is_running:
            reply = QMessageBox.question(
                self,
                "Confirm Exit",
                "Processing is in progress. Are you sure you want to exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            
            self._orchestrator.stop()
        
        event.accept()


def run_app():
    """Run the application"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
