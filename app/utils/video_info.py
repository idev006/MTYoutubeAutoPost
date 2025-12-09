"""
Video Info Service
Extract video metadata using FFprobe
"""

import subprocess
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class VideoMetadata:
    """Video metadata container"""
    width: int = 0
    height: int = 0
    duration_seconds: float = 0.0
    file_size: int = 0
    codec: str = ""
    framerate: float = 0.0
    bitrate: int = 0
    
    @property
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio"""
        if self.height == 0:
            return 0
        return self.width / self.height
    
    @property
    def video_type(self) -> str:
        """
        Determine video type based on aspect ratio
        - 16:9 (1.77) = regular video
        - 9:16 (0.56) = short
        """
        if self.aspect_ratio >= 1.0:
            return "video"
        else:
            return "short"
    
    @property
    def is_short(self) -> bool:
        """Is this a YouTube Short?"""
        return self.video_type == "short"
    
    @property
    def duration_formatted(self) -> str:
        """Format duration as HH:MM:SS"""
        total_seconds = int(self.duration_seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"


class VideoInfoService:
    """
    Extract video metadata using FFprobe
    """
    
    SUPPORTED_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
    
    @classmethod
    def is_video_file(cls, file_path: Path) -> bool:
        """Check if file is a supported video format"""
        return file_path.suffix.lower() in cls.SUPPORTED_EXTENSIONS
    
    @classmethod
    def get_metadata(cls, file_path: str) -> Optional[VideoMetadata]:
        """
        Get video metadata using FFprobe
        
        Args:
            file_path: Path to video file
            
        Returns:
            VideoMetadata or None if failed
        """
        path = Path(file_path)
        
        if not path.exists():
            logger.error(f"Video file not found: {file_path}")
            return None
        
        try:
            # Run ffprobe
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                # FFprobe not available, use fallback
                logger.warning(f"FFprobe failed, using fallback metadata for: {path.name}")
                return cls._get_fallback_metadata(path)
            
            data = json.loads(result.stdout)
            
            # Find video stream
            video_stream = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                logger.warning(f"No video stream found in: {path.name}")
                return cls._get_fallback_metadata(path)
            
            # Extract metadata
            format_info = data.get('format', {})
            
            # Calculate framerate
            framerate = 0.0
            r_frame_rate = video_stream.get('r_frame_rate', '0/1')
            if '/' in r_frame_rate:
                num, den = r_frame_rate.split('/')
                if int(den) > 0:
                    framerate = int(num) / int(den)
            
            metadata = VideoMetadata(
                width=int(video_stream.get('width', 0)),
                height=int(video_stream.get('height', 0)),
                duration_seconds=float(format_info.get('duration', 0)),
                file_size=int(format_info.get('size', path.stat().st_size)),
                codec=video_stream.get('codec_name', ''),
                framerate=framerate,
                bitrate=int(format_info.get('bit_rate', 0))
            )
            
            logger.debug(f"Video metadata: {path.name} - {metadata.width}x{metadata.height}, {metadata.duration_formatted}")
            return metadata
            
        except subprocess.TimeoutExpired:
            logger.error(f"FFprobe timeout for: {path.name}")
            return cls._get_fallback_metadata(path)
        except json.JSONDecodeError:
            logger.error(f"FFprobe output parse error for: {path.name}")
            return cls._get_fallback_metadata(path)
        except FileNotFoundError:
            logger.warning("FFprobe not found, using fallback metadata")
            return cls._get_fallback_metadata(path)
        except Exception as e:
            logger.error(f"Failed to get video metadata: {e}")
            return cls._get_fallback_metadata(path)
    
    @classmethod
    def _get_fallback_metadata(cls, path: Path) -> VideoMetadata:
        """
        Get basic metadata without FFprobe
        """
        return VideoMetadata(
            width=1920,  # Assume 16:9
            height=1080,
            duration_seconds=0.0,
            file_size=path.stat().st_size if path.exists() else 0,
            codec="unknown",
            framerate=30.0,
            bitrate=0
        )
    
    @classmethod
    def detect_video_type(cls, file_path: str) -> str:
        """
        Detect if video is regular (16:9) or short (9:16)
        
        Returns:
            'video' or 'short'
        """
        metadata = cls.get_metadata(file_path)
        if metadata:
            return metadata.video_type
        return "video"  # Default
    
    @classmethod
    def get_duration(cls, file_path: str) -> float:
        """Get video duration in seconds"""
        metadata = cls.get_metadata(file_path)
        if metadata:
            return metadata.duration_seconds
        return 0.0
    
    @classmethod
    def get_file_size(cls, file_path: str) -> int:
        """Get file size in bytes"""
        path = Path(file_path)
        if path.exists():
            return path.stat().st_size
        return 0


# Convenience functions
def get_video_metadata(file_path: str) -> Optional[VideoMetadata]:
    """Get video metadata"""
    return VideoInfoService.get_metadata(file_path)


def detect_video_type(file_path: str) -> str:
    """Detect video type (video or short)"""
    return VideoInfoService.detect_video_type(file_path)


def is_video_file(file_path: Path) -> bool:
    """Check if file is a video"""
    return VideoInfoService.is_video_file(file_path)
