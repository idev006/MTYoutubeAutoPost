"""
Pydantic Schemas for prod.json validation
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class AffiliateUrl(BaseModel):
    """Single affiliate URL entry"""
    label: str = Field(..., description="Display label for the URL")
    url: str = Field(..., description="Affiliate URL")
    is_primary: bool = Field(default=False, description="Whether this is the primary link")


class PlaylistConfig(BaseModel):
    """Playlist configuration"""
    playlist_id: Optional[str] = Field(default=None, description="Existing playlist ID")
    playlist_name: Optional[str] = Field(default=None, description="Playlist name (create if not exists)")
    create_if_not_exists: bool = Field(default=True, description="Create playlist if not found")


class ProdDetail(BaseModel):
    """Product details section"""
    prod_code: str = Field(..., description="Unique product code (SKU)")
    prod_name: str = Field(..., description="Product name")
    prod_short_descr: str = Field(..., description="Short description for title")
    prod_long_descr: Optional[str] = Field(default="", description="Long description for YouTube")
    prod_tags: list[str] = Field(default_factory=list, description="Tags for SEO")
    category_id: int = Field(default=22, description="YouTube category ID")
    privacy: str = Field(default="public", description="Video privacy setting")
    
    @field_validator('privacy')
    @classmethod
    def validate_privacy(cls, v: str) -> str:
        valid = ['public', 'unlisted', 'private']
        if v not in valid:
            raise ValueError(f"Privacy must be one of {valid}")
        return v


class AffDetail(BaseModel):
    """Affiliate details section"""
    platform: str = Field(default="shopee", description="Affiliate platform")
    urls_list: list[AffiliateUrl] = Field(default_factory=list, description="List of affiliate URLs")
    discount_code: Optional[str] = Field(default=None, description="Discount code")


class UploadConfig(BaseModel):
    """Upload configuration section"""
    made_for_kids: bool = Field(default=False, description="Is content made for kids?")
    notify_subscribers: bool = Field(default=True, description="Notify subscribers on upload")
    embeddable: bool = Field(default=True, description="Allow embedding")


class ScheduleConfig(BaseModel):
    """Schedule configuration for timed publishing"""
    enabled: bool = Field(default=False, description="Enable scheduled publishing")
    start_datetime: Optional[str] = Field(default=None, description="Start datetime ISO format (e.g. 2024-12-11T10:00:00)")
    interval_hours: float = Field(default=4.0, description="Hours between each video publish")
    timezone: str = Field(default="Asia/Bangkok", description="Timezone for scheduling")


class ProdJsonSchema(BaseModel):
    """
    Main schema for prod.json file
    This is the root schema that validates the entire prod.json structure
    """
    schema_version: str = Field(default="1.0", description="Schema version")
    prod_detail: ProdDetail = Field(..., description="Product details")
    playlist: Optional[PlaylistConfig] = Field(default=None, description="Playlist configuration")
    aff_detail: AffDetail = Field(..., description="Affiliate details")
    upload_config: Optional[UploadConfig] = Field(default_factory=UploadConfig, description="Upload settings")
    schedule: Optional[ScheduleConfig] = Field(default_factory=ScheduleConfig, description="Schedule settings")
    
    class Config:
        extra = 'ignore'  # Ignore extra fields


class VideoTask(BaseModel):
    """
    Internal schema for a video upload/update task
    Created from prod.json + discovered video files
    """
    # Task identification
    task_id: str = Field(..., description="Unique task ID")
    session_id: str = Field(..., description="Upload session ID")
    
    # Product info
    prod_code: str
    prod_name: str
    prod_short_descr: str
    prod_long_descr: str = ""
    prod_tags: list[str] = Field(default_factory=list)
    category_id: int = 22
    privacy: str = "unlisted"
    
    # Video file
    filename: str
    file_path: str
    file_size: int = 0
    video_type: str = "video"  # 'video' or 'short'
    duration_seconds: float = 0.0
    episode: int = 1
    
    # Affiliate
    aff_urls: list[AffiliateUrl] = Field(default_factory=list)
    discount_code: Optional[str] = None
    
    # Playlist
    playlist_id: Optional[str] = None
    playlist_name: Optional[str] = None
    create_playlist: bool = True
    
    # Upload config
    made_for_kids: bool = False
    notify_subscribers: bool = True
    
    # Status
    status: str = "pending"  # pending, uploading, completed, failed, skipped
    progress: float = 0.0
    retry_count: int = 0
    error_message: Optional[str] = None
    
    # YouTube result (after upload)
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None
    
    # Action
    action: str = "upload"  # 'upload' or 'update'
    existing_video_id: Optional[str] = None  # For update action
    
    # Schedule
    scheduled_publish_at: Optional[str] = None  # ISO datetime for scheduled publish
    
    def get_title(self) -> str:
        """Generate YouTube title"""
        base = f"{self.prod_code}-{self.prod_name}-{self.prod_short_descr}"
        if self.episode > 0:
            return f"{base} ep.{self.episode}"
        return base
    
    def get_primary_aff_url(self) -> Optional[str]:
        """Get primary affiliate URL"""
        for url in self.aff_urls:
            if url.is_primary:
                return url.url
        return self.aff_urls[0].url if self.aff_urls else None


class DuplicateCheckResult(BaseModel):
    """Result of duplicate check"""
    exists: bool = False
    prod_code: str = ""
    episode: int = 1
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None
    title: Optional[str] = None
