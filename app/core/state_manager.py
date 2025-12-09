"""
State Manager
Handles state persistence for crash recovery
Saves and loads task state from database
"""

import uuid
from datetime import datetime
from typing import Optional
from loguru import logger

from app.models.database import db, UploadSession, Video, Product
from app.models.schemas import VideoTask


class StateManager:
    """
    Manages application state for crash recovery
    Saves task progress to database, allows resuming after crash
    """
    
    _current_session_id: Optional[str] = None
    
    @classmethod
    def create_session(cls) -> str:
        """
        Create a new upload session
        
        Returns:
            session_id
        """
        session_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        with db.get_session() as session:
            new_session = UploadSession(
                session_id=session_id,
                status='pending',
                started_at=now
            )
            session.add(new_session)
        
        cls._current_session_id = session_id
        logger.info(f"Created upload session: {session_id}")
        return session_id
    
    @classmethod
    def get_current_session_id(cls) -> Optional[str]:
        """Get current session ID"""
        return cls._current_session_id
    
    @classmethod
    def set_session_status(cls, session_id: str, status: str):
        """Update session status"""
        with db.get_session() as session:
            upload_session = session.query(UploadSession).filter_by(
                session_id=session_id
            ).first()
            
            if upload_session:
                upload_session.status = status
                if status == 'completed':
                    upload_session.completed_at = datetime.now().isoformat()
        
        logger.info(f"Session {session_id} status: {status}")
    
    @classmethod
    def save_task_state(cls, task: VideoTask):
        """
        Save task state to database
        Called when task status changes
        """
        with db.get_session() as session:
            # Find or create product
            product = session.query(Product).filter_by(
                prod_code=task.prod_code
            ).first()
            
            if not product:
                now = datetime.now().isoformat()
                product = Product(
                    prod_code=task.prod_code,
                    prod_name=task.prod_name,
                    prod_short_descr=task.prod_short_descr,
                    prod_long_descr=task.prod_long_descr,
                    created_at=now,
                    updated_at=now
                )
                session.add(product)
                session.flush()
            
            # Find or create video
            video = session.query(Video).filter_by(
                product_id=product.id,
                episode=task.episode
            ).first()
            
            now = datetime.now().isoformat()
            
            if video:
                # Update existing
                video.status = task.status
                video.progress = task.progress
                video.youtube_video_id = task.youtube_video_id
                video.youtube_url = task.youtube_url
                video.error_message = task.error_message
                video.retry_count = task.retry_count
                if task.status == 'completed':
                    video.uploaded_at = now
            else:
                # Create new
                video = Video(
                    product_id=product.id,
                    filename=task.filename,
                    file_path=task.file_path,
                    file_size=task.file_size,
                    video_type=task.video_type,
                    duration_seconds=task.duration_seconds,
                    episode=task.episode,
                    status=task.status,
                    progress=task.progress,
                    youtube_video_id=task.youtube_video_id,
                    youtube_url=task.youtube_url,
                    error_message=task.error_message,
                    retry_count=task.retry_count,
                    created_at=now
                )
                session.add(video)
        
        logger.debug(f"Saved task state: {task.prod_code} ep.{task.episode} - {task.status}")
    
    @classmethod
    def get_pending_tasks(cls, session_id: Optional[str] = None) -> list[dict]:
        """
        Get all pending/failed tasks from database
        Used for crash recovery
        
        Returns:
            List of task dicts
        """
        pending_tasks = []
        
        with db.get_session() as session:
            # Find videos that are not completed
            query = session.query(Video).filter(
                Video.status.in_(['pending', 'uploading', 'failed'])
            )
            
            videos = query.all()
            
            for video in videos:
                product = session.query(Product).filter_by(
                    id=video.product_id
                ).first()
                
                if product:
                    pending_tasks.append({
                        'prod_code': product.prod_code,
                        'prod_name': product.prod_name,
                        'prod_short_descr': product.prod_short_descr or '',
                        'prod_long_descr': product.prod_long_descr or '',
                        'filename': video.filename,
                        'file_path': video.file_path,
                        'episode': video.episode,
                        'status': video.status,
                        'retry_count': video.retry_count or 0,
                        'error_message': video.error_message
                    })
        
        logger.info(f"Found {len(pending_tasks)} pending tasks")
        return pending_tasks
    
    @classmethod
    def get_resumable_session(cls) -> Optional[str]:
        """
        Check if there's a session that can be resumed
        
        Returns:
            session_id if found, None otherwise
        """
        with db.get_session() as session:
            # Find most recent non-completed session
            upload_session = session.query(UploadSession).filter(
                UploadSession.status.in_(['pending', 'running', 'paused'])
            ).order_by(UploadSession.started_at.desc()).first()
            
            if upload_session:
                logger.info(f"Found resumable session: {upload_session.session_id}")
                return upload_session.session_id
        
        return None
    
    @classmethod
    def mark_task_status(
        cls,
        prod_code: str,
        episode: int,
        status: str,
        youtube_video_id: Optional[str] = None,
        youtube_url: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """Update task status in database"""
        with db.get_session() as session:
            product = session.query(Product).filter_by(
                prod_code=prod_code
            ).first()
            
            if product:
                video = session.query(Video).filter_by(
                    product_id=product.id,
                    episode=episode
                ).first()
                
                if video:
                    video.status = status
                    if youtube_video_id:
                        video.youtube_video_id = youtube_video_id
                        video.youtube_url = youtube_url
                    if error_message:
                        video.error_message = error_message
                    if status == 'completed':
                        video.uploaded_at = datetime.now().isoformat()
        
        logger.debug(f"Marked {prod_code} ep.{episode} as {status}")
    
    @classmethod
    def update_session_stats(cls, session_id: str, uploaded: int, updated: int, failed: int, skipped: int):
        """Update session statistics"""
        with db.get_session() as session:
            upload_session = session.query(UploadSession).filter_by(
                session_id=session_id
            ).first()
            
            if upload_session:
                upload_session.uploaded_count = uploaded
                upload_session.updated_count = updated
                upload_session.failed_count = failed
                upload_session.skipped_count = skipped


# Convenience functions
def save_task_state(task: VideoTask):
    """Save task state"""
    StateManager.save_task_state(task)


def get_pending_tasks() -> list[dict]:
    """Get pending tasks for recovery"""
    return StateManager.get_pending_tasks()
