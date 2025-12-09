"""
Worker Manager
Manages pool of upload workers with thread-safe task queue
"""

import queue
from typing import Optional
from threading import Lock
from PySide6.QtCore import QObject, Signal
from loguru import logger

from app.models.schemas import VideoTask
from app.workers.upload_worker import UploadWorker
from app.config import config


class WorkerManager(QObject):
    """
    Manages a pool of upload workers
    Thread-safe task queue management
    
    Signals:
        all_tasks_completed(): All tasks in queue completed
        progress_updated(task_id, percent): Individual task progress
        task_completed(task_id, youtube_id, youtube_url): Task completed
        task_failed(task_id, error_message): Task failed
    """
    
    # Signals
    all_tasks_completed = Signal()
    progress_updated = Signal(str, float)
    task_completed = Signal(str, str, str)
    task_failed = Signal(str, str)
    status_changed = Signal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._workers: list[UploadWorker] = []
        self._task_queue: queue.Queue[VideoTask] = queue.Queue()
        self._lock = Lock()
        self._is_running = False
        self._worker_count = config.worker_count
        self._delay_range = config.delay_range
        
        # Statistics
        self._total_tasks = 0
        self._completed_count = 0
        self._failed_count = 0
        
        logger.info(f"WorkerManager initialized - {self._worker_count} workers")
    
    @property
    def worker_count(self) -> int:
        return self._worker_count
    
    @worker_count.setter
    def worker_count(self, value: int):
        self._worker_count = max(1, min(5, value))
        config.worker_count = self._worker_count
    
    @property
    def delay_range(self) -> tuple[int, int]:
        return self._delay_range
    
    @delay_range.setter
    def delay_range(self, value: tuple[int, int]):
        self._delay_range = value
        config.delay_range = value
    
    @property
    def queue_size(self) -> int:
        return self._task_queue.qsize()
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    @property
    def completed_count(self) -> int:
        return self._completed_count
    
    @property
    def failed_count(self) -> int:
        return self._failed_count
    
    @property
    def remaining_count(self) -> int:
        return self._total_tasks - self._completed_count - self._failed_count
    
    def set_worker_count(self, count: int):
        """Set number of workers (1-5)"""
        self.worker_count = count
        logger.info(f"Worker count set to {self._worker_count}")
    
    def set_delay_range(self, from_ss: int, to_ss: int):
        """Set delay range in seconds"""
        self.delay_range = (from_ss, to_ss)
        logger.info(f"Delay range set to {from_ss}-{to_ss}s")
    
    def add_task(self, task: VideoTask):
        """Add task to queue (thread-safe)"""
        with self._lock:
            self._task_queue.put(task)
            self._total_tasks += 1
        logger.debug(f"Task added: {task.prod_code} ep.{task.episode}")
    
    def add_tasks(self, tasks: list[VideoTask]):
        """Add multiple tasks to queue"""
        for task in tasks:
            self.add_task(task)
        logger.info(f"Added {len(tasks)} tasks to queue")
    
    def clear_queue(self):
        """Clear all pending tasks"""
        with self._lock:
            while not self._task_queue.empty():
                try:
                    self._task_queue.get_nowait()
                except queue.Empty:
                    break
            self._total_tasks = 0
            self._completed_count = 0
            self._failed_count = 0
        logger.info("Task queue cleared")
    
    def start_workers(self, count: Optional[int] = None):
        """Start worker threads"""
        if self._is_running:
            logger.warning("Workers already running")
            return
        
        if count:
            self.worker_count = count
        
        self._is_running = True
        
        # Create workers
        for i in range(self._worker_count):
            worker = UploadWorker(
                worker_id=i + 1,
                delay_range=self._delay_range,
                parent=None
            )
            
            # Connect signals
            worker.progress_updated.connect(self._on_progress_updated)
            worker.task_completed.connect(self._on_task_completed)
            worker.task_failed.connect(self._on_task_failed)
            worker.status_changed.connect(self._on_status_changed)
            
            self._workers.append(worker)
            worker.start()
        
        logger.info(f"Started {len(self._workers)} workers")
        
        # Start task distribution
        self._distribute_tasks()
    
    def stop_all(self):
        """Stop all workers gracefully"""
        self._is_running = False
        
        for worker in self._workers:
            worker.stop()
        
        # Wait for workers to finish
        for worker in self._workers:
            worker.wait(5000)  # 5 second timeout
        
        self._workers.clear()
        logger.info("All workers stopped")
    
    def pause_all(self):
        """Pause all workers"""
        for worker in self._workers:
            worker.pause()
        logger.info("All workers paused")
    
    def resume_all(self):
        """Resume all workers"""
        for worker in self._workers:
            worker.resume()
        logger.info("All workers resumed")
        self._distribute_tasks()
    
    def get_status(self) -> dict:
        """Get current status"""
        return {
            'is_running': self._is_running,
            'worker_count': len(self._workers),
            'queue_size': self.queue_size,
            'total_tasks': self._total_tasks,
            'completed_count': self._completed_count,
            'failed_count': self._failed_count,
            'remaining_count': self.remaining_count
        }
    
    def _distribute_tasks(self):
        """Distribute tasks to available workers"""
        if not self._is_running:
            return
        
        for worker in self._workers:
            if not worker.is_busy:
                try:
                    task = self._task_queue.get_nowait()
                    worker.set_task(task)
                except queue.Empty:
                    break
    
    def _on_progress_updated(self, task_id: str, percent: float):
        """Handle progress update from worker"""
        self.progress_updated.emit(task_id, percent)
    
    def _on_task_completed(self, task_id: str, youtube_id: str, youtube_url: str):
        """Handle task completion"""
        with self._lock:
            self._completed_count += 1
        
        self.task_completed.emit(task_id, youtube_id, youtube_url)
        
        # Check if all done
        if self.remaining_count <= 0 and self._task_queue.empty():
            self.all_tasks_completed.emit()
        else:
            # Distribute more tasks
            self._distribute_tasks()
    
    def _on_task_failed(self, task_id: str, error_message: str):
        """Handle task failure"""
        with self._lock:
            self._failed_count += 1
        
        self.task_failed.emit(task_id, error_message)
        
        # Check if all done
        if self.remaining_count <= 0 and self._task_queue.empty():
            self.all_tasks_completed.emit()
        else:
            # Distribute more tasks
            self._distribute_tasks()
    
    def _on_status_changed(self, task_id: str, status: str):
        """Handle status change"""
        self.status_changed.emit(task_id, status)
