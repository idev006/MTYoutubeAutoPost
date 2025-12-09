"""
Prod.json Parser
Parses and validates prod.json files using Pydantic
Builds VideoTask objects for upload queue
"""

import uuid
from pathlib import Path
from typing import Optional
from loguru import logger

from app.models.schemas import (
    ProdJsonSchema, VideoTask, AffiliateUrl,
    ProdDetail, AffDetail, PlaylistConfig, UploadConfig
)
from app.core.scanner import ScannedFolder, ScannedVideo


class ProdJsonParser:
    """
    Parses prod.json and builds VideoTask list
    """
    
    @classmethod
    def parse(cls, data: dict) -> Optional[ProdJsonSchema]:
        """
        Parse and validate prod.json data
        
        Args:
            data: Raw dict from JSON file
            
        Returns:
            Validated ProdJsonSchema or None if invalid
        """
        try:
            return ProdJsonSchema(**data)
        except Exception as e:
            logger.error(f"Failed to parse prod.json: {e}")
            return None
    
    @classmethod
    def parse_file(cls, file_path: str) -> Optional[ProdJsonSchema]:
        """Parse prod.json from file path"""
        import json
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls.parse(data)
        except Exception as e:
            logger.error(f"Failed to read prod.json from {file_path}: {e}")
            return None
    
    @classmethod
    def build_video_tasks(
        cls,
        folder: ScannedFolder,
        session_id: str
    ) -> list[VideoTask]:
        """
        Build VideoTask objects from ScannedFolder
        
        Args:
            folder: ScannedFolder with prod.json and videos
            session_id: Upload session ID
            
        Returns:
            List of VideoTask objects ready for upload queue
        """
        if not folder.is_valid or not folder.prod_json_data:
            logger.warning(f"Cannot build tasks from invalid folder: {folder.folder_name}")
            return []
        
        # Parse prod.json
        prod_json = cls.parse(folder.prod_json_data)
        if not prod_json:
            return []
        
        tasks = []
        
        for video in folder.videos:
            task = cls._create_video_task(
                prod_json=prod_json,
                video=video,
                session_id=session_id,
                folder_path=folder.folder_path
            )
            tasks.append(task)
        
        logger.info(f"Created {len(tasks)} video tasks from {folder.folder_name}")
        return tasks
    
    @classmethod
    def _create_video_task(
        cls,
        prod_json: ProdJsonSchema,
        video: ScannedVideo,
        session_id: str,
        folder_path: str
    ) -> VideoTask:
        """Create a single VideoTask from prod.json and video info"""
        
        prod = prod_json.prod_detail
        aff = prod_json.aff_detail
        playlist = prod_json.playlist
        upload_cfg = prod_json.upload_config or UploadConfig()
        
        # Convert AffiliateUrl list
        aff_urls = [
            AffiliateUrl(
                label=url.label,
                url=url.url,
                is_primary=url.is_primary
            )
            for url in aff.urls_list
        ] if aff.urls_list else []
        
        # Determine video type
        video_type = "video"
        duration = 0.0
        if video.metadata:
            video_type = video.metadata.video_type
            duration = video.metadata.duration_seconds
        
        task = VideoTask(
            # Task identification
            task_id=str(uuid.uuid4()),
            session_id=session_id,
            
            # Product info
            prod_code=prod.prod_code,
            prod_name=prod.prod_name,
            prod_short_descr=prod.prod_short_descr,
            prod_long_descr=prod.prod_long_descr or "",
            prod_tags=prod.prod_tags,
            category_id=prod.category_id,
            privacy=prod.privacy,
            
            # Video file
            filename=video.filename,
            file_path=video.file_path,
            file_size=video.file_size,
            video_type=video_type,
            duration_seconds=duration,
            episode=video.episode,
            
            # Affiliate
            aff_urls=aff_urls,
            discount_code=aff.discount_code,
            
            # Playlist
            playlist_id=playlist.playlist_id if playlist else None,
            playlist_name=playlist.playlist_name if playlist else None,
            create_playlist=playlist.create_if_not_exists if playlist else False,
            
            # Upload config
            made_for_kids=upload_cfg.made_for_kids,
            notify_subscribers=upload_cfg.notify_subscribers,
            
            # Status
            status="pending",
            progress=0.0,
            retry_count=0,
            action="upload"  # Will be changed to "update" if duplicate found
        )
        
        return task
    
    @classmethod
    def validate_required_fields(cls, data: dict) -> tuple[bool, list[str]]:
        """
        Validate required fields in prod.json
        
        Returns:
            (is_valid, list of error messages)
        """
        errors = []
        
        # Check prod_detail
        prod_detail = data.get('prod_detail', {})
        if not prod_detail:
            errors.append("Missing prod_detail section")
        else:
            if not prod_detail.get('prod_code'):
                errors.append("Missing prod_code")
            if not prod_detail.get('prod_name'):
                errors.append("Missing prod_name")
            if not prod_detail.get('prod_short_descr'):
                errors.append("Missing prod_short_descr")
        
        # Check aff_detail
        aff_detail = data.get('aff_detail', {})
        if not aff_detail:
            errors.append("Missing aff_detail section")
        
        return len(errors) == 0, errors


# Convenience functions
def parse_prod_json(file_path: str) -> Optional[ProdJsonSchema]:
    """Parse prod.json file"""
    return ProdJsonParser.parse_file(file_path)


def build_video_tasks(folder: ScannedFolder, session_id: str) -> list[VideoTask]:
    """Build video tasks from scanned folder"""
    return ProdJsonParser.build_video_tasks(folder, session_id)
