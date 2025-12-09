"""
YouTube API Service
Handles OAuth2 authentication, video upload, update, and listing
Thread-safe implementation
"""

import os
import json
import pickle
from pathlib import Path
from typing import Optional, Callable, Any
from threading import Lock
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from loguru import logger

from app.config import config


class YouTubeAPIService:
    """
    Thread-safe YouTube API service
    Handles OAuth2, video upload, update, and channel video listing
    """
    
    _instance: Optional['YouTubeAPIService'] = None
    _lock = Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._api_lock = Lock()
        self._youtube = None
        self._credentials = None
        self._initialized = True
        
        # Paths
        self._client_secrets_path = config.client_secrets_path
        self._token_path = config.youtube_token_path
        self._scopes = config.youtube_scopes
        
        logger.info("YouTubeAPIService initialized")
    
    @property
    def is_authenticated(self) -> bool:
        """Check if we have valid credentials"""
        return self._credentials is not None and self._credentials.valid
    
    def authenticate(self, force_refresh: bool = False) -> bool:
        """
        Authenticate with YouTube API using OAuth2
        
        Args:
            force_refresh: Force re-authentication even if valid credentials exist
            
        Returns:
            True if authentication successful
        """
        with self._api_lock:
            try:
                # Try to load existing credentials
                if not force_refresh and self._token_path.exists():
                    with open(self._token_path, 'rb') as token:
                        self._credentials = pickle.load(token)
                
                # Check if credentials are valid
                if self._credentials and self._credentials.expired and self._credentials.refresh_token:
                    logger.info("Refreshing expired credentials...")
                    self._credentials.refresh(Request())
                
                # If no valid credentials, start OAuth flow
                if not self._credentials or not self._credentials.valid:
                    if not self._client_secrets_path.exists():
                        logger.error(f"Client secrets not found: {self._client_secrets_path}")
                        logger.error("Please download client_secrets.json from Google Cloud Console")
                        return False
                    
                    logger.info("Starting OAuth2 flow...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self._client_secrets_path),
                        self._scopes
                    )
                    self._credentials = flow.run_local_server(port=8080)
                
                # Save credentials
                self._token_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._token_path, 'wb') as token:
                    pickle.dump(self._credentials, token)
                
                # Build YouTube service
                self._youtube = build('youtube', 'v3', credentials=self._credentials)
                logger.info("YouTube API authentication successful")
                return True
                
            except Exception as e:
                logger.error(f"Authentication failed: {e}")
                return False
    
    def _ensure_authenticated(self):
        """Ensure we have valid credentials before API calls"""
        if not self.is_authenticated:
            if not self.authenticate():
                raise RuntimeError("YouTube API not authenticated")
    
    # ========================================
    # VIDEO UPLOAD
    # ========================================
    
    def upload_video(
        self,
        file_path: str,
        title: str,
        description: str,
        tags: list[str] = None,
        category_id: int = 22,
        privacy: str = "unlisted",
        made_for_kids: bool = False,
        notify_subscribers: bool = True,
        progress_callback: Callable[[float], None] = None
    ) -> Optional[dict]:
        """
        Upload a video to YouTube
        
        Args:
            file_path: Path to video file
            title: Video title (max 100 chars)
            description: Video description (max 5000 chars)
            tags: List of tags
            category_id: YouTube category ID
            privacy: 'public', 'unlisted', or 'private'
            made_for_kids: Whether video is made for kids
            notify_subscribers: Notify subscribers on upload
            progress_callback: Callback for upload progress (0.0 - 100.0)
            
        Returns:
            dict with video_id and url on success, None on failure
        """
        self._ensure_authenticated()
        
        with self._api_lock:
            try:
                # Prepare metadata
                body = {
                    'snippet': {
                        'title': title[:100],  # Max 100 chars
                        'description': description[:5000],  # Max 5000 chars
                        'tags': tags or [],
                        'categoryId': str(category_id)
                    },
                    'status': {
                        'privacyStatus': privacy,
                        'selfDeclaredMadeForKids': made_for_kids,
                        'notifySubscribers': notify_subscribers
                    }
                }
                
                # Create media upload
                media = MediaFileUpload(
                    file_path,
                    mimetype='video/*',
                    resumable=True,
                    chunksize=1024 * 1024 * 8  # 8MB chunks
                )
                
                # Create upload request
                request = self._youtube.videos().insert(
                    part='snippet,status',
                    body=body,
                    media_body=media
                )
                
                # Execute upload with progress tracking
                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status and progress_callback:
                        progress_callback(status.progress() * 100)
                
                video_id = response['id']
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                logger.info(f"Video uploaded successfully: {video_url}")
                
                return {
                    'video_id': video_id,
                    'url': video_url,
                    'title': title,
                    'response': response
                }
                
            except HttpError as e:
                logger.error(f"Upload failed (HTTP {e.resp.status}): {e.content}")
                return None
            except Exception as e:
                logger.error(f"Upload failed: {e}")
                return None
    
    # ========================================
    # VIDEO UPDATE
    # ========================================
    
    def update_video(
        self,
        video_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        category_id: Optional[int] = None,
        privacy: Optional[str] = None
    ) -> bool:
        """
        Update video metadata
        
        Args:
            video_id: YouTube video ID
            title: New title (optional)
            description: New description (optional)
            tags: New tags (optional)
            category_id: New category (optional)
            privacy: New privacy status (optional)
            
        Returns:
            True on success
        """
        self._ensure_authenticated()
        
        with self._api_lock:
            try:
                # Get current video data
                current = self._youtube.videos().list(
                    part='snippet,status',
                    id=video_id
                ).execute()
                
                if not current.get('items'):
                    logger.error(f"Video not found: {video_id}")
                    return False
                
                video = current['items'][0]
                snippet = video['snippet']
                status = video['status']
                
                # Update fields if provided
                if title is not None:
                    snippet['title'] = title[:100]
                if description is not None:
                    snippet['description'] = description[:5000]
                if tags is not None:
                    snippet['tags'] = tags
                if category_id is not None:
                    snippet['categoryId'] = str(category_id)
                if privacy is not None:
                    status['privacyStatus'] = privacy
                
                # Execute update
                self._youtube.videos().update(
                    part='snippet,status',
                    body={
                        'id': video_id,
                        'snippet': snippet,
                        'status': status
                    }
                ).execute()
                
                logger.info(f"Video updated: {video_id}")
                return True
                
            except HttpError as e:
                logger.error(f"Update failed (HTTP {e.resp.status}): {e.content}")
                return False
            except Exception as e:
                logger.error(f"Update failed: {e}")
                return False
    
    # ========================================
    # VIDEO LISTING (for duplicate check)
    # ========================================
    
    def list_channel_videos(self, max_results: int = 500) -> list[dict]:
        """
        List all videos from the authenticated channel
        Used to sync local cache for duplicate detection
        
        Args:
            max_results: Maximum number of videos to retrieve
            
        Returns:
            List of video metadata dicts
        """
        self._ensure_authenticated()
        
        videos = []
        
        with self._api_lock:
            try:
                # Get channel's uploads playlist
                channels = self._youtube.channels().list(
                    part='contentDetails',
                    mine=True
                ).execute()
                
                if not channels.get('items'):
                    logger.warning("No channel found for authenticated user")
                    return []
                
                uploads_playlist_id = channels['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                
                # Get all videos from uploads playlist
                next_page_token = None
                while len(videos) < max_results:
                    playlist_response = self._youtube.playlistItems().list(
                        part='snippet,contentDetails',
                        playlistId=uploads_playlist_id,
                        maxResults=min(50, max_results - len(videos)),
                        pageToken=next_page_token
                    ).execute()
                    
                    for item in playlist_response.get('items', []):
                        video_id = item['contentDetails']['videoId']
                        snippet = item['snippet']
                        
                        videos.append({
                            'video_id': video_id,
                            'url': f"https://www.youtube.com/watch?v={video_id}",
                            'title': snippet.get('title', ''),
                            'description': snippet.get('description', ''),
                            'published_at': snippet.get('publishedAt', ''),
                            'thumbnail': snippet.get('thumbnails', {}).get('default', {}).get('url', '')
                        })
                    
                    next_page_token = playlist_response.get('nextPageToken')
                    if not next_page_token:
                        break
                
                logger.info(f"Retrieved {len(videos)} videos from channel")
                return videos
                
            except HttpError as e:
                logger.error(f"List videos failed (HTTP {e.resp.status}): {e.content}")
                return []
            except Exception as e:
                logger.error(f"List videos failed: {e}")
                return []
    
    def search_video_by_title(self, query: str, max_results: int = 10) -> list[dict]:
        """
        Search for videos by title in the authenticated channel
        
        Args:
            query: Search query (title keyword)
            max_results: Maximum results to return
            
        Returns:
            List of matching videos
        """
        self._ensure_authenticated()
        
        with self._api_lock:
            try:
                response = self._youtube.search().list(
                    part='snippet',
                    forMine=True,
                    type='video',
                    q=query,
                    maxResults=max_results
                ).execute()
                
                videos = []
                for item in response.get('items', []):
                    video_id = item['id']['videoId']
                    snippet = item['snippet']
                    
                    videos.append({
                        'video_id': video_id,
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'title': snippet.get('title', ''),
                        'description': snippet.get('description', ''),
                        'published_at': snippet.get('publishedAt', '')
                    })
                
                return videos
                
            except HttpError as e:
                logger.error(f"Search failed (HTTP {e.resp.status}): {e.content}")
                return []
            except Exception as e:
                logger.error(f"Search failed: {e}")
                return []
    
    # ========================================
    # PLAYLIST OPERATIONS
    # ========================================
    
    def list_playlists(self, max_results: int = 50) -> list[dict]:
        """List all playlists from the authenticated channel"""
        self._ensure_authenticated()
        
        playlists = []
        
        with self._api_lock:
            try:
                next_page_token = None
                while len(playlists) < max_results:
                    response = self._youtube.playlists().list(
                        part='snippet,contentDetails',
                        mine=True,
                        maxResults=min(50, max_results - len(playlists)),
                        pageToken=next_page_token
                    ).execute()
                    
                    for item in response.get('items', []):
                        playlists.append({
                            'playlist_id': item['id'],
                            'title': item['snippet']['title'],
                            'description': item['snippet'].get('description', ''),
                            'video_count': item['contentDetails']['itemCount'],
                            'privacy': item['status']['privacyStatus'] if 'status' in item else 'public'
                        })
                    
                    next_page_token = response.get('nextPageToken')
                    if not next_page_token:
                        break
                
                logger.info(f"Retrieved {len(playlists)} playlists")
                return playlists
                
            except HttpError as e:
                logger.error(f"List playlists failed: {e.content}")
                return []
            except Exception as e:
                logger.error(f"List playlists failed: {e}")
                return []
    
    def create_playlist(
        self,
        title: str,
        description: str = "",
        privacy: str = "public"
    ) -> Optional[dict]:
        """Create a new playlist"""
        self._ensure_authenticated()
        
        with self._api_lock:
            try:
                response = self._youtube.playlists().insert(
                    part='snippet,status',
                    body={
                        'snippet': {
                            'title': title,
                            'description': description
                        },
                        'status': {
                            'privacyStatus': privacy
                        }
                    }
                ).execute()
                
                playlist_id = response['id']
                logger.info(f"Created playlist: {title} ({playlist_id})")
                
                return {
                    'playlist_id': playlist_id,
                    'title': title,
                    'description': description,
                    'privacy': privacy
                }
                
            except HttpError as e:
                logger.error(f"Create playlist failed: {e.content}")
                return None
            except Exception as e:
                logger.error(f"Create playlist failed: {e}")
                return None
    
    def add_to_playlist(self, playlist_id: str, video_id: str) -> bool:
        """Add a video to a playlist"""
        self._ensure_authenticated()
        
        with self._api_lock:
            try:
                self._youtube.playlistItems().insert(
                    part='snippet',
                    body={
                        'snippet': {
                            'playlistId': playlist_id,
                            'resourceId': {
                                'kind': 'youtube#video',
                                'videoId': video_id
                            }
                        }
                    }
                ).execute()
                
                logger.info(f"Added video {video_id} to playlist {playlist_id}")
                return True
                
            except HttpError as e:
                if e.resp.status == 409:  # Already in playlist
                    logger.warning(f"Video {video_id} already in playlist {playlist_id}")
                    return True
                logger.error(f"Add to playlist failed: {e.content}")
                return False
            except Exception as e:
                logger.error(f"Add to playlist failed: {e}")
                return False
    
    def get_or_create_playlist(self, name: str, description: str = "") -> Optional[str]:
        """
        Get playlist by name, or create if not exists
        
        Returns:
            playlist_id or None
        """
        # Search existing playlists
        playlists = self.list_playlists()
        for pl in playlists:
            if pl['title'].lower() == name.lower():
                logger.info(f"Found existing playlist: {name}")
                return pl['playlist_id']
        
        # Create new playlist
        result = self.create_playlist(name, description)
        if result:
            return result['playlist_id']
        
        return None


# Global instance
youtube_api = YouTubeAPIService()
