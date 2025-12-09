"""
Duplicate Checker
Checks if prod_code+episode already exists on YouTube channel
Syncs and caches channel videos in database
"""

import re
from typing import Optional
from datetime import datetime
from loguru import logger

from app.models.database import db, YouTubeChannelVideo
from app.models.schemas import DuplicateCheckResult
from app.services.youtube_api import youtube_api
from app.services.template_engine import TemplateEngine


class DuplicateChecker:
    """
    Checks for duplicate videos on YouTube
    Uses prod_code + episode as unique identifier
    Caches channel videos in database for fast lookups
    """
    
    @classmethod
    def sync_channel_videos(cls, force: bool = False) -> int:
        """
        Sync all videos from YouTube channel to local database
        
        Args:
            force: Force re-sync even if recently synced
            
        Returns:
            Number of videos synced
        """
        try:
            # Get all videos from channel
            videos = youtube_api.list_channel_videos(max_results=1000)
            
            if not videos:
                logger.warning("No videos found in channel or not authenticated")
                return 0
            
            synced_count = 0
            now = datetime.now().isoformat()
            
            with db.get_session() as session:
                for video in videos:
                    # Extract prod_code and episode from title
                    prod_code, episode = TemplateEngine.extract_prod_code_from_title(
                        video.get('title', '')
                    )
                    
                    # Check if already exists
                    existing = session.query(YouTubeChannelVideo).filter_by(
                        youtube_video_id=video['video_id']
                    ).first()
                    
                    if existing:
                        # Update existing
                        existing.title = video.get('title', '')
                        existing.description = video.get('description', '')
                        existing.prod_code = prod_code or existing.prod_code
                        existing.episode = episode or existing.episode
                        existing.last_synced_at = now
                    else:
                        # Create new
                        new_video = YouTubeChannelVideo(
                            youtube_video_id=video['video_id'],
                            youtube_url=video['url'],
                            prod_code=prod_code or '',
                            episode=episode or 1,
                            title=video.get('title', ''),
                            description=video.get('description', ''),
                            uploaded_at=video.get('published_at', ''),
                            last_synced_at=now
                        )
                        session.add(new_video)
                        synced_count += 1
            
            logger.info(f"Synced {synced_count} new videos from channel (total: {len(videos)})")
            return synced_count
            
        except Exception as e:
            logger.error(f"Failed to sync channel videos: {e}")
            return 0
    
    @classmethod
    def check_duplicate(
        cls,
        prod_code: str,
        episode: int = 1
    ) -> DuplicateCheckResult:
        """
        Check if a video with prod_code+episode already exists
        
        Args:
            prod_code: Product code (SKU)
            episode: Episode number
            
        Returns:
            DuplicateCheckResult with exists flag and YouTube data
        """
        result = DuplicateCheckResult(
            exists=False,
            prod_code=prod_code,
            episode=episode
        )
        
        try:
            # First check local cache
            with db.get_session() as session:
                existing = session.query(YouTubeChannelVideo).filter_by(
                    prod_code=prod_code,
                    episode=episode
                ).first()
                
                if existing:
                    result.exists = True
                    result.youtube_video_id = existing.youtube_video_id
                    result.youtube_url = existing.youtube_url
                    result.title = existing.title
                    logger.debug(f"Found duplicate in cache: {prod_code} ep.{episode}")
                    return result
            
            # If not in cache, try searching YouTube directly
            search_query = f"{prod_code} ep.{episode}"
            search_results = youtube_api.search_video_by_title(search_query, max_results=5)
            
            for video in search_results:
                # Extract prod_code from title
                title_prod_code, title_episode = TemplateEngine.extract_prod_code_from_title(
                    video.get('title', '')
                )
                
                if title_prod_code == prod_code and title_episode == episode:
                    result.exists = True
                    result.youtube_video_id = video['video_id']
                    result.youtube_url = video['url']
                    result.title = video.get('title', '')
                    
                    # Cache this result
                    cls._cache_video(video, prod_code, episode)
                    
                    logger.info(f"Found duplicate via search: {prod_code} ep.{episode}")
                    return result
            
            logger.debug(f"No duplicate found: {prod_code} ep.{episode}")
            return result
            
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return result
    
    @classmethod
    def _cache_video(cls, video: dict, prod_code: str, episode: int):
        """Cache a video in the database"""
        try:
            now = datetime.now().isoformat()
            
            with db.get_session() as session:
                existing = session.query(YouTubeChannelVideo).filter_by(
                    youtube_video_id=video['video_id']
                ).first()
                
                if not existing:
                    new_video = YouTubeChannelVideo(
                        youtube_video_id=video['video_id'],
                        youtube_url=video['url'],
                        prod_code=prod_code,
                        episode=episode,
                        title=video.get('title', ''),
                        description=video.get('description', ''),
                        uploaded_at=video.get('published_at', ''),
                        last_synced_at=now
                    )
                    session.add(new_video)
                    
        except Exception as e:
            logger.error(f"Failed to cache video: {e}")
    
    @classmethod
    def get_youtube_url(cls, prod_code: str, episode: int = 1) -> Optional[str]:
        """Get YouTube URL for a prod_code+episode if exists"""
        result = cls.check_duplicate(prod_code, episode)
        return result.youtube_url if result.exists else None
    
    @classmethod
    def get_youtube_video_id(cls, prod_code: str, episode: int = 1) -> Optional[str]:
        """Get YouTube video ID for a prod_code+episode if exists"""
        result = cls.check_duplicate(prod_code, episode)
        return result.youtube_video_id if result.exists else None
    
    @classmethod
    def build_duplicate_cache(cls) -> dict[str, DuplicateCheckResult]:
        """
        Build a cache of all duplicates from database
        
        Returns:
            Dict mapping "prod_code_ep{episode}" to DuplicateCheckResult
        """
        cache = {}
        
        try:
            with db.get_session() as session:
                videos = session.query(YouTubeChannelVideo).filter(
                    YouTubeChannelVideo.prod_code != ''
                ).all()
                
                for video in videos:
                    key = f"{video.prod_code}_ep{video.episode}"
                    cache[key] = DuplicateCheckResult(
                        exists=True,
                        prod_code=video.prod_code,
                        episode=video.episode,
                        youtube_video_id=video.youtube_video_id,
                        youtube_url=video.youtube_url,
                        title=video.title
                    )
            
            logger.info(f"Built duplicate cache with {len(cache)} entries")
            
        except Exception as e:
            logger.error(f"Failed to build duplicate cache: {e}")
        
        return cache
    
    @classmethod
    def register_uploaded_video(
        cls,
        prod_code: str,
        episode: int,
        youtube_video_id: str,
        youtube_url: str,
        title: str,
        description: str = "",
        aff_urls: str = ""
    ):
        """
        Register a newly uploaded video in the cache
        """
        try:
            now = datetime.now().isoformat()
            
            with db.get_session() as session:
                new_video = YouTubeChannelVideo(
                    youtube_video_id=youtube_video_id,
                    youtube_url=youtube_url,
                    prod_code=prod_code,
                    episode=episode,
                    title=title,
                    description=description,
                    aff_urls=aff_urls,
                    uploaded_at=now,
                    last_synced_at=now
                )
                session.add(new_video)
            
            logger.info(f"Registered uploaded video: {prod_code} ep.{episode}")
            
        except Exception as e:
            logger.error(f"Failed to register uploaded video: {e}")


# Convenience functions
def check_duplicate(prod_code: str, episode: int = 1) -> DuplicateCheckResult:
    """Check if duplicate exists"""
    return DuplicateChecker.check_duplicate(prod_code, episode)


def sync_channel_videos() -> int:
    """Sync channel videos to local cache"""
    return DuplicateChecker.sync_channel_videos()
