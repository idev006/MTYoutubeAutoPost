"""
SQLAlchemy Database Setup
Thread-safe SQLite connection with all table definitions
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Float, Boolean,
    ForeignKey, Index, CheckConstraint, event
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from sqlalchemy.pool import StaticPool
from loguru import logger

from app.config import config

Base = declarative_base()


# ========================================
# PRODUCTS TABLE
# ========================================
class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    prod_code = Column(String, unique=True, nullable=False, index=True)
    prod_name = Column(String, nullable=False)
    prod_short_descr = Column(Text)
    prod_long_descr = Column(Text)
    prod_tags = Column(Text)  # JSON array
    category_id = Column(Integer, default=22)
    playlist_id = Column(String)
    playlist_name = Column(String)
    
    # Affiliate
    aff_urls = Column(Text)  # JSON array
    discount_code = Column(String)
    
    # Metadata
    source_folder = Column(String)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    
    # Relationships
    videos = relationship("Video", back_populates="product", cascade="all, delete-orphan")


# ========================================
# VIDEOS TABLE
# ========================================
class Video(Base):
    __tablename__ = 'videos'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    
    # File Info
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    video_type = Column(String)  # 'video' or 'short'
    duration_seconds = Column(Float)
    episode = Column(Integer, default=1)
    
    # YouTube
    youtube_video_id = Column(String, index=True)
    youtube_url = Column(String)
    youtube_title = Column(String)
    
    # Status
    status = Column(String, default='pending')  # pending, uploading, completed, failed, skipped
    progress = Column(Float, default=0.0)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(String, nullable=False)
    uploaded_at = Column(String)
    
    # Relationships
    product = relationship("Product", back_populates="videos")
    
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'uploading', 'completed', 'failed', 'skipped')"),
        CheckConstraint("video_type IN ('video', 'short')"),
        Index('idx_videos_status', 'status'),
    )


# ========================================
# UPLOAD_SESSIONS TABLE
# ========================================
class UploadSession(Base):
    __tablename__ = 'upload_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, unique=True, nullable=False)
    
    # Statistics
    total_videos = Column(Integer, default=0)
    uploaded_count = Column(Integer, default=0)
    updated_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    
    # Status
    status = Column(String, default='pending')  # pending, running, completed, paused, cancelled
    
    # Timestamps
    started_at = Column(String)
    completed_at = Column(String)
    
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'completed', 'paused', 'cancelled')"),
    )


# ========================================
# YOUTUBE_CHANNEL_VIDEOS TABLE (Duplicate Check + URL Storage)
# ========================================
class YouTubeChannelVideo(Base):
    __tablename__ = 'youtube_channel_videos'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # YouTube Data
    youtube_video_id = Column(String, unique=True, nullable=False)
    youtube_url = Column(String, nullable=False, index=True)
    
    # Product Mapping
    prod_code = Column(String, nullable=False, index=True)
    episode = Column(Integer, default=1)
    
    # Metadata
    title = Column(String)
    description = Column(Text)
    tags = Column(Text)  # JSON array
    privacy = Column(String)
    playlist_id = Column(String)
    
    # Affiliate
    aff_urls = Column(Text)  # JSON array
    
    # Status
    video_type = Column(String)  # 'video' or 'short'
    duration_seconds = Column(Float)
    view_count = Column(Integer)
    
    # Timestamps
    uploaded_at = Column(String)
    last_synced_at = Column(String, nullable=False)
    last_updated_at = Column(String)
    
    __table_args__ = (
        Index('idx_channel_prod_episode', 'prod_code', 'episode'),
    )


# ========================================
# PLAYLISTS TABLE (Cache)
# ========================================
class Playlist(Base):
    __tablename__ = 'playlists'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    youtube_playlist_id = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    privacy = Column(String, default='public')
    video_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(String)
    last_synced_at = Column(String, nullable=False)


# ========================================
# DATABASE MANAGER
# ========================================
class DatabaseManager:
    """Thread-safe database manager"""
    
    _instance: Optional['DatabaseManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize database connection"""
        db_path = config.db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # SQLite with thread safety
        self.engine = create_engine(
            f'sqlite:///{db_path}',
            connect_args={'check_same_thread': False},
            poolclass=StaticPool,
            echo=False
        )
        
        # Enable foreign keys
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        
        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        
        # Create tables
        Base.metadata.create_all(self.engine)
        logger.info(f"Database initialized: {db_path}")
    
    @contextmanager
    def get_session(self) -> Session:
        """Get a thread-safe session context"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()
    
    def get_now(self) -> str:
        """Get current timestamp as ISO string"""
        return datetime.now().isoformat()


# Global instance
db = DatabaseManager()
