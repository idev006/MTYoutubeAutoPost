"""
Upload Worker
QThread-based worker for uploading videos to YouTube
Thread-safe with signals for progress updates
"""

import time
import random
from typing import Optional
from PySide6.QtCore import QThread, Signal, QMutex
from loguru import logger

from app.models.schemas import VideoTask
from app.services.youtube_api import youtube_api
from app.services.template_engine import TemplateEngine
from app.core.duplicate_checker import DuplicateChecker


class UploadWorker(QThread):
    """
    Worker thread for uploading/updating videos
    
    Signals:
        progress_updated(task_id, percent): Upload progress
        task_completed(task_id, youtube_id, youtube_url): Task completed
        task_failed(task_id, error_message): Task failed
        status_changed(task_id, status): Status changed
    """
    
    # Signals
    progress_updated = Signal(str, float)  # task_id, percent
    task_completed = Signal(str, str, str)  # task_id, youtube_id, youtube_url
    task_failed = Signal(str, str)  # task_id, error_message
    status_changed = Signal(str, str)  # task_id, status
    
    def __init__(
        self,
        worker_id: int,
        delay_range: tuple[int, int] = (30, 120),
        parent=None
    ):
        super().__init__(parent)
        
        self.worker_id = worker_id
        self.delay_range = delay_range
        
        self._task: Optional[VideoTask] = None
        self._mutex = QMutex()
        self._running = True
        self._paused = False
        
        logger.info(f"Worker {worker_id} initialized")
    
    @property
    def is_busy(self) -> bool:
        """Check if worker is processing a task"""
        self._mutex.lock()
        busy = self._task is not None
        self._mutex.unlock()
        return busy
    
    def set_task(self, task: VideoTask):
        """Set task for worker to process"""
        self._mutex.lock()
        self._task = task
        self._mutex.unlock()
    
    def pause(self):
        """Pause worker"""
        self._paused = True
        logger.info(f"Worker {self.worker_id} paused")
    
    def resume(self):
        """Resume worker"""
        self._paused = False
        logger.info(f"Worker {self.worker_id} resumed")
    
    def stop(self):
        """Stop worker"""
        self._running = False
        logger.info(f"Worker {self.worker_id} stopping")
    
    def run(self):
        """Main worker loop"""
        logger.info(f"Worker {self.worker_id} started")
        
        while self._running:
            # Check for pause
            while self._paused and self._running:
                time.sleep(0.5)
            
            if not self._running:
                break
            
            # Get task
            self._mutex.lock()
            task = self._task
            self._task = None
            self._mutex.unlock()
            
            if task:
                self._process_task(task)
            else:
                # No task, sleep a bit
                time.sleep(0.1)
        
        logger.info(f"Worker {self.worker_id} stopped")
    
    def _process_task(self, task: VideoTask):
        """Process a single upload/update task"""
        try:
            # Random delay before starting (anti-bot)
            delay = random.randint(self.delay_range[0], self.delay_range[1])
            logger.info(f"Worker {self.worker_id}: Waiting {delay}s before processing {task.prod_code} ep.{task.episode}")
            
            # Wait with periodic pause checks
            for _ in range(delay * 2):
                if not self._running:
                    return
                while self._paused and self._running:
                    time.sleep(0.5)
                time.sleep(0.5)
            
            # Update status
            self.status_changed.emit(task.task_id, "uploading")
            
            # Generate title and description
            title = TemplateEngine.generate_title_from_task(task)
            description = TemplateEngine.generate_description_from_task(task)
            tags = TemplateEngine.generate_tags(task.prod_tags)
            
            if task.action == "update" and task.existing_video_id:
                # UPDATE existing video
                self._update_video(task, title, description, tags)
            else:
                # UPLOAD new video
                self._upload_video(task, title, description, tags)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Worker {self.worker_id}: Task failed - {error_msg}")
            self.task_failed.emit(task.task_id, error_msg)
    
    def _upload_video(self, task: VideoTask, title: str, description: str, tags: list[str]):
        """Upload a new video"""
        logger.info(f"Worker {self.worker_id}: Uploading {task.filename}")
        
        def progress_callback(percent: float):
            self.progress_updated.emit(task.task_id, percent)
        
        result = youtube_api.upload_video(
            file_path=task.file_path,
            title=title,
            description=description,
            tags=tags,
            category_id=task.category_id,
            privacy=task.privacy,
            made_for_kids=task.made_for_kids,
            notify_subscribers=task.notify_subscribers,
            progress_callback=progress_callback
        )
        
        if result:
            video_id = result['video_id']
            video_url = result['url']
            
            # Register in duplicate cache
            DuplicateChecker.register_uploaded_video(
                prod_code=task.prod_code,
                episode=task.episode,
                youtube_video_id=video_id,
                youtube_url=video_url,
                title=title,
                description=description
            )
            
            # Handle playlist
            if task.playlist_id or task.playlist_name:
                self._add_to_playlist(task, video_id)
            
            logger.info(f"Worker {self.worker_id}: Upload complete - {video_url}")
            self.task_completed.emit(task.task_id, video_id, video_url)
        else:
            self.task_failed.emit(task.task_id, "Upload failed")
    
    def _update_video(self, task: VideoTask, title: str, description: str, tags: list[str]):
        """Update existing video metadata"""
        logger.info(f"Worker {self.worker_id}: Updating {task.existing_video_id}")
        
        success = youtube_api.update_video(
            video_id=task.existing_video_id,
            title=title,
            description=description,
            tags=tags,
            category_id=task.category_id
        )
        
        if success:
            video_url = f"https://www.youtube.com/watch?v={task.existing_video_id}"
            
            # Handle playlist
            if task.playlist_id or task.playlist_name:
                self._add_to_playlist(task, task.existing_video_id)
            
            logger.info(f"Worker {self.worker_id}: Update complete - {video_url}")
            self.task_completed.emit(task.task_id, task.existing_video_id, video_url)
        else:
            self.task_failed.emit(task.task_id, "Update failed")
    
    def _add_to_playlist(self, task: VideoTask, video_id: str):
        """Add video to playlist"""
        try:
            playlist_id = task.playlist_id
            
            # Create playlist if needed
            if not playlist_id and task.playlist_name and task.create_playlist:
                playlist_id = youtube_api.get_or_create_playlist(task.playlist_name)
            
            if playlist_id:
                youtube_api.add_to_playlist(playlist_id, video_id)
                
        except Exception as e:
            logger.warning(f"Failed to add to playlist: {e}")
