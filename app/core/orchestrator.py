"""
Orchestrator
Main controller that coordinates all components
Handles start/pause/stop/resume operations
"""

import uuid
from typing import Optional
from PySide6.QtCore import QObject, Signal
from loguru import logger

from app.config import config
from app.models.schemas import VideoTask
from app.core.scanner import FolderScanner, ScannedFolder
from app.core.parser import ProdJsonParser
from app.core.duplicate_checker import DuplicateChecker
from app.core.state_manager import StateManager
from app.workers.worker_manager import WorkerManager


class Orchestrator(QObject):
    """
    Main orchestrator that coordinates upload operations
    
    Responsibilities:
    - Scan folders and build task queue
    - Check for duplicates
    - Manage worker lifecycle (start/pause/stop/resume)
    - Handle crash recovery
    
    Signals:
        started(): Processing started
        paused(): Processing paused
        resumed(): Processing resumed
        stopped(): Processing stopped
        completed(): All tasks completed
        progress_updated(total, completed, failed): Overall progress
        task_status_changed(task_id, status): Individual task status
    """
    
    # Signals
    started = Signal()
    paused = Signal()
    resumed = Signal()
    stopped = Signal()
    completed = Signal()
    progress_updated = Signal(int, int, int)  # total, completed, failed
    task_status_changed = Signal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._worker_manager = WorkerManager()
        self._session_id: Optional[str] = None
        self._tasks: list[VideoTask] = []
        self._is_running = False
        self._is_paused = False
        
        # Connect worker manager signals
        self._worker_manager.task_completed.connect(self._on_task_completed)
        self._worker_manager.task_failed.connect(self._on_task_failed)
        self._worker_manager.all_tasks_completed.connect(self._on_all_completed)
        self._worker_manager.status_changed.connect(self._on_status_changed)
        
        logger.info("Orchestrator initialized")
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    @property
    def is_paused(self) -> bool:
        return self._is_paused
    
    @property
    def session_id(self) -> Optional[str]:
        return self._session_id
    
    @property
    def task_count(self) -> int:
        return len(self._tasks)
    
    def set_worker_count(self, count: int):
        """Set number of worker threads"""
        self._worker_manager.set_worker_count(count)
    
    def set_delay_range(self, from_ss: int, to_ss: int):
        """Set random delay range"""
        self._worker_manager.set_delay_range(from_ss, to_ss)
    
    # ========================================
    # FOLDER PROCESSING
    # ========================================
    
    def process_folders(self, folder_paths: list[str]) -> list[VideoTask]:
        """
        Scan folders and build task queue
        
        Args:
            folder_paths: List of folder paths to process
            
        Returns:
            List of VideoTask objects
        """
        # Create session
        self._session_id = StateManager.create_session()
        self._tasks = []
        
        # Scan folders
        scanned_folders = FolderScanner.scan_folders(folder_paths)
        valid_folders = FolderScanner.get_valid_folders(scanned_folders)
        
        if not valid_folders:
            logger.warning("No valid folders found")
            return []
        
        # Build tasks from each folder
        for folder in valid_folders:
            tasks = ProdJsonParser.build_video_tasks(folder, self._session_id)
            
            # Check for duplicates and set action
            for task in tasks:
                result = DuplicateChecker.check_duplicate(task.prod_code, task.episode)
                
                if result.exists:
                    task.action = "update"
                    task.existing_video_id = result.youtube_video_id
                    task.youtube_url = result.youtube_url
                    logger.info(f"Duplicate found: {task.prod_code} ep.{task.episode} -> Update")
                else:
                    task.action = "upload"
                    logger.info(f"New video: {task.prod_code} ep.{task.episode} -> Upload")
                
                self._tasks.append(task)
                
                # Save initial state
                StateManager.save_task_state(task)
        
        logger.info(f"Prepared {len(self._tasks)} tasks from {len(valid_folders)} folders")
        return self._tasks
    
    def process_folder(self, folder_path: str) -> list[VideoTask]:
        """Process a single folder"""
        return self.process_folders([folder_path])
    
    # ========================================
    # CONTROL METHODS
    # ========================================
    
    def start(self):
        """Start processing tasks"""
        if self._is_running:
            logger.warning("Already running")
            return
        
        if not self._tasks:
            logger.warning("No tasks to process")
            return
        
        self._is_running = True
        self._is_paused = False
        
        # Update session status
        if self._session_id:
            StateManager.set_session_status(self._session_id, 'running')
        
        # Add tasks to worker queue
        self._worker_manager.add_tasks(self._tasks)
        
        # Start workers
        self._worker_manager.start_workers()
        
        logger.info("Processing started")
        self.started.emit()
    
    def pause(self):
        """Pause processing"""
        if not self._is_running or self._is_paused:
            return
        
        self._is_paused = True
        self._worker_manager.pause_all()
        
        if self._session_id:
            StateManager.set_session_status(self._session_id, 'paused')
        
        logger.info("Processing paused")
        self.paused.emit()
    
    def resume(self):
        """Resume processing"""
        if not self._is_running or not self._is_paused:
            return
        
        self._is_paused = False
        self._worker_manager.resume_all()
        
        if self._session_id:
            StateManager.set_session_status(self._session_id, 'running')
        
        logger.info("Processing resumed")
        self.resumed.emit()
    
    def stop(self):
        """Stop processing"""
        if not self._is_running:
            return
        
        self._is_running = False
        self._is_paused = False
        self._worker_manager.stop_all()
        
        if self._session_id:
            StateManager.set_session_status(self._session_id, 'cancelled')
        
        logger.info("Processing stopped")
        self.stopped.emit()
    
    # ========================================
    # CRASH RECOVERY
    # ========================================
    
    def resume_from_crash(self) -> bool:
        """
        Check for and resume from a previous session
        
        Returns:
            True if resumed, False if no session to resume
        """
        session_id = StateManager.get_resumable_session()
        
        if not session_id:
            logger.info("No session to resume")
            return False
        
        # Get pending tasks
        pending_tasks = StateManager.get_pending_tasks(session_id)
        
        if not pending_tasks:
            logger.info("No pending tasks to resume")
            return False
        
        self._session_id = session_id
        self._tasks = []
        
        # Rebuild task objects
        for task_data in pending_tasks:
            task = VideoTask(
                task_id=str(uuid.uuid4()),
                session_id=session_id,
                prod_code=task_data['prod_code'],
                prod_name=task_data['prod_name'],
                prod_short_descr=task_data['prod_short_descr'],
                prod_long_descr=task_data.get('prod_long_descr', ''),
                filename=task_data['filename'],
                file_path=task_data['file_path'],
                episode=task_data['episode'],
                status='pending',
                retry_count=task_data.get('retry_count', 0)
            )
            self._tasks.append(task)
        
        logger.info(f"Recovered {len(self._tasks)} tasks from session {session_id}")
        return True
    
    def check_resumable_session(self) -> Optional[str]:
        """Check if there's a session that can be resumed"""
        return StateManager.get_resumable_session()
    
    # ========================================
    # STATUS & STATISTICS
    # ========================================
    
    def get_status(self) -> dict:
        """Get current orchestrator status"""
        worker_status = self._worker_manager.get_status()
        
        return {
            'is_running': self._is_running,
            'is_paused': self._is_paused,
            'session_id': self._session_id,
            'total_tasks': len(self._tasks),
            **worker_status
        }
    
    # ========================================
    # SIGNAL HANDLERS
    # ========================================
    
    def _on_task_completed(self, task_id: str, youtube_id: str, youtube_url: str):
        """Handle task completion"""
        # Find and update task
        for task in self._tasks:
            if task.task_id == task_id:
                task.status = 'completed'
                task.youtube_video_id = youtube_id
                task.youtube_url = youtube_url
                StateManager.save_task_state(task)
                break
        
        self._update_progress()
        self.task_status_changed.emit(task_id, 'completed')
    
    def _on_task_failed(self, task_id: str, error_message: str):
        """Handle task failure"""
        for task in self._tasks:
            if task.task_id == task_id:
                task.status = 'failed'
                task.error_message = error_message
                StateManager.save_task_state(task)
                break
        
        self._update_progress()
        self.task_status_changed.emit(task_id, 'failed')
    
    def _on_all_completed(self):
        """Handle all tasks completed"""
        self._is_running = False
        
        if self._session_id:
            StateManager.set_session_status(self._session_id, 'completed')
        
        logger.info("All tasks completed")
        self.completed.emit()
    
    def _on_status_changed(self, task_id: str, status: str):
        """Handle status change"""
        for task in self._tasks:
            if task.task_id == task_id:
                task.status = status
                StateManager.save_task_state(task)
                break
        
        self.task_status_changed.emit(task_id, status)
    
    def _update_progress(self):
        """Update progress signal"""
        total = len(self._tasks)
        completed = sum(1 for t in self._tasks if t.status == 'completed')
        failed = sum(1 for t in self._tasks if t.status == 'failed')
        
        self.progress_updated.emit(total, completed, failed)
        
        # Update session stats
        if self._session_id:
            uploaded = sum(1 for t in self._tasks if t.status == 'completed' and t.action == 'upload')
            updated = sum(1 for t in self._tasks if t.status == 'completed' and t.action == 'update')
            StateManager.update_session_stats(self._session_id, uploaded, updated, failed, 0)


# Global instance
orchestrator = Orchestrator()
