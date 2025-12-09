"""
Folder Scanner
Scans folders for prod.json and video files
"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from loguru import logger

from app.utils.video_info import VideoInfoService, VideoMetadata


@dataclass
class ScannedVideo:
    """Represents a video file found in a folder"""
    filename: str
    file_path: str
    file_size: int
    episode: int
    metadata: Optional[VideoMetadata] = None
    
    @property
    def video_type(self) -> str:
        """Get video type (video or short)"""
        if self.metadata:
            return self.metadata.video_type
        return "video"


@dataclass
class ScannedFolder:
    """Represents a scanned product folder"""
    folder_path: str
    folder_name: str
    has_prod_json: bool = False
    prod_json_path: Optional[str] = None
    prod_json_data: Optional[dict] = None
    videos: list[ScannedVideo] = field(default_factory=list)
    thumbnail_path: Optional[str] = None
    is_valid: bool = False
    validation_errors: list[str] = field(default_factory=list)
    
    @property
    def video_count(self) -> int:
        return len(self.videos)
    
    @property
    def prod_code(self) -> Optional[str]:
        """Get prod_code from prod.json data"""
        if self.prod_json_data:
            prod_detail = self.prod_json_data.get('prod_detail', {})
            return prod_detail.get('prod_code')
        return None


class FolderScanner:
    """
    Scans folders for prod.json and video files
    Auto-assigns episode numbers based on filename alphabetical order
    """
    
    PROD_JSON_FILENAME = "prod.json"
    THUMBNAIL_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
    
    @classmethod
    def scan_folder(cls, folder_path: str) -> ScannedFolder:
        """
        Scan a single folder for prod.json and videos
        
        Args:
            folder_path: Path to folder
            
        Returns:
            ScannedFolder with all discovered data
        """
        path = Path(folder_path)
        
        result = ScannedFolder(
            folder_path=str(path),
            folder_name=path.name
        )
        
        if not path.exists():
            result.validation_errors.append("Folder does not exist")
            return result
        
        if not path.is_dir():
            result.validation_errors.append("Path is not a directory")
            return result
        
        # Check for prod.json
        prod_json_path = path / cls.PROD_JSON_FILENAME
        if prod_json_path.exists():
            result.has_prod_json = True
            result.prod_json_path = str(prod_json_path)
            
            # Parse prod.json
            try:
                with open(prod_json_path, 'r', encoding='utf-8') as f:
                    result.prod_json_data = json.load(f)
            except json.JSONDecodeError as e:
                result.validation_errors.append(f"Invalid JSON: {e}")
            except Exception as e:
                result.validation_errors.append(f"Error reading prod.json: {e}")
        else:
            result.validation_errors.append("No prod.json found")
        
        # Find video files
        video_files = []
        for file in path.iterdir():
            if file.is_file() and VideoInfoService.is_video_file(file):
                video_files.append(file)
        
        # Sort by filename for consistent episode ordering
        video_files.sort(key=lambda f: f.name.lower())
        
        # Create video entries with episode numbers
        for i, video_file in enumerate(video_files, start=1):
            metadata = VideoInfoService.get_metadata(str(video_file))
            
            video = ScannedVideo(
                filename=video_file.name,
                file_path=str(video_file),
                file_size=video_file.stat().st_size,
                episode=i,
                metadata=metadata
            )
            result.videos.append(video)
        
        if not result.videos:
            result.validation_errors.append("No video files found")
        
        # Find thumbnail
        for file in path.iterdir():
            if file.is_file() and file.suffix.lower() in cls.THUMBNAIL_EXTENSIONS:
                # Prefer files named "thumbnail" or "thumb"
                if 'thumb' in file.stem.lower():
                    result.thumbnail_path = str(file)
                    break
                # Otherwise use first image found
                if result.thumbnail_path is None:
                    result.thumbnail_path = str(file)
        
        # Validate
        result.is_valid = (
            result.has_prod_json and
            result.prod_json_data is not None and
            len(result.videos) > 0 and
            result.prod_code is not None
        )
        
        if result.is_valid:
            logger.info(f"Valid folder: {path.name} - {len(result.videos)} videos, prod_code: {result.prod_code}")
        else:
            logger.warning(f"Invalid folder: {path.name} - {result.validation_errors}")
        
        return result
    
    @classmethod
    def scan_folders(cls, folder_paths: list[str]) -> list[ScannedFolder]:
        """
        Scan multiple folders
        
        Args:
            folder_paths: List of folder paths
            
        Returns:
            List of ScannedFolder objects
        """
        results = []
        for folder_path in folder_paths:
            result = cls.scan_folder(folder_path)
            results.append(result)
        
        valid_count = sum(1 for r in results if r.is_valid)
        logger.info(f"Scanned {len(results)} folders, {valid_count} valid")
        
        return results
    
    @classmethod
    def scan_parent_folder(cls, parent_path: str) -> list[ScannedFolder]:
        """
        Scan all subdirectories of a parent folder
        
        Args:
            parent_path: Path to parent folder
            
        Returns:
            List of ScannedFolder objects for each subdirectory
        """
        path = Path(parent_path)
        
        if not path.exists() or not path.is_dir():
            logger.error(f"Invalid parent folder: {parent_path}")
            return []
        
        subfolders = [str(f) for f in path.iterdir() if f.is_dir()]
        return cls.scan_folders(subfolders)
    
    @classmethod
    def get_valid_folders(cls, folders: list[ScannedFolder]) -> list[ScannedFolder]:
        """Filter to only valid folders"""
        return [f for f in folders if f.is_valid]


# Convenience functions
def scan_folder(folder_path: str) -> ScannedFolder:
    """Scan a single folder"""
    return FolderScanner.scan_folder(folder_path)


def scan_folders(folder_paths: list[str]) -> list[ScannedFolder]:
    """Scan multiple folders"""
    return FolderScanner.scan_folders(folder_paths)
