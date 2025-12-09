"""
Qt Signals for thread-safe UI communication
"""

from PySide6.QtCore import QObject, Signal


class UISignals(QObject):
    """
    Custom signals for worker → UI communication
    Thread-safe signal emission for UI updates
    """
    
    # Progress signals
    upload_progress = Signal(str, float)  # task_id, percent
    overall_progress = Signal(int, int, int)  # total, completed, failed
    
    # Task signals
    task_started = Signal(str)  # task_id
    task_completed = Signal(str, str, str)  # task_id, youtube_id, youtube_url
    task_failed = Signal(str, str)  # task_id, error_message
    task_status_changed = Signal(str, str)  # task_id, status
    
    # Session signals
    session_started = Signal(str)  # session_id
    session_paused = Signal()
    session_resumed = Signal()
    session_stopped = Signal()
    session_completed = Signal()
    
    # Folder signals
    folder_scanned = Signal(str, int, bool)  # folder_path, video_count, is_valid
    folders_ready = Signal(int)  # total_tasks
    
    # Log signals
    log_message = Signal(str, str)  # level, message
    
    # Error signals
    error_occurred = Signal(str, str)  # error_type, error_message


# Global signals instance
ui_signals = UISignals()
