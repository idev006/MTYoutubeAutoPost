"""
API Key Manager
Manages multiple YouTube API credentials with automatic rotation
"""

import os
import json
import glob
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from threading import Lock
from loguru import logger

from app.config import CONFIG_DIR


class APIKeyManager:
    """
    Manages multiple YouTube API credentials
    Automatically switches to next key when quota exceeded
    
    Keys are stored as:
    - ytkey_1.json
    - ytkey_2.json
    - etc.
    """
    
    _instance: Optional['APIKeyManager'] = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the key manager"""
        self._keys: list[dict] = []
        self._current_index = 0
        self._exhausted_keys: dict[int, datetime] = {}  # index -> exhausted_time
        self._quota_reset_hour = 7  # 00:00 PST = 07:00 UTC = 14:00 Thailand
        
        self._load_all_keys()
        logger.info(f"APIKeyManager initialized with {len(self._keys)} keys")
    
    def _load_all_keys(self):
        """Load all ytkey_*.json files"""
        pattern = str(CONFIG_DIR / "ytkey_*.json")
        key_files = sorted(glob.glob(pattern))
        
        self._keys = []
        for filepath in key_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    key_data = json.load(f)
                    key_data['_filepath'] = filepath
                    key_data['_name'] = Path(filepath).stem
                    self._keys.append(key_data)
                    logger.debug(f"Loaded key: {Path(filepath).name}")
            except Exception as e:
                logger.error(f"Failed to load {filepath}: {e}")
        
        if not self._keys:
            logger.warning("No API keys found! Looking for ytkey_*.json in config folder")
    
    @property
    def total_keys(self) -> int:
        """Total number of available keys"""
        return len(self._keys)
    
    @property
    def available_keys(self) -> int:
        """Number of keys not exhausted"""
        self._cleanup_exhausted()
        return len(self._keys) - len(self._exhausted_keys)
    
    @property
    def current_key_name(self) -> str:
        """Name of current key"""
        if self._keys:
            return self._keys[self._current_index].get('_name', 'unknown')
        return 'none'
    
    def get_current_credentials_path(self) -> Optional[Path]:
        """Get path to current credentials file"""
        if not self._keys:
            return None
        return Path(self._keys[self._current_index]['_filepath'])
    
    def get_current_credentials(self) -> Optional[dict]:
        """Get current credentials data"""
        if not self._keys:
            return None
        return self._keys[self._current_index]
    
    def mark_quota_exceeded(self) -> bool:
        """
        Mark current key as quota exceeded and switch to next
        
        Returns:
            True if switched to new key, False if all keys exhausted
        """
        with self._lock:
            # Mark current as exhausted
            self._exhausted_keys[self._current_index] = datetime.now()
            logger.warning(f"Key {self.current_key_name} quota exceeded, marked as exhausted")
            
            # Try to find next available key
            return self._switch_to_next_available()
    
    def _switch_to_next_available(self) -> bool:
        """Switch to next available key"""
        self._cleanup_exhausted()
        
        # Find next non-exhausted key
        for i in range(len(self._keys)):
            next_index = (self._current_index + 1 + i) % len(self._keys)
            if next_index not in self._exhausted_keys:
                self._current_index = next_index
                logger.info(f"Switched to key: {self.current_key_name}")
                return True
        
        logger.error("All API keys exhausted! No available keys.")
        return False
    
    def _cleanup_exhausted(self):
        """Remove keys from exhausted list if quota has reset"""
        # Quota resets at 00:00 PST (Pacific Time)
        # That's 07:00 UTC or 14:00 in Thailand
        now = datetime.now()
        
        # Calculate last reset time
        today_reset = now.replace(hour=self._quota_reset_hour, minute=0, second=0, microsecond=0)
        if now < today_reset:
            # Reset hasn't happened today, use yesterday's reset
            last_reset = today_reset - timedelta(days=1)
        else:
            last_reset = today_reset
        
        # Remove keys exhausted before last reset
        keys_to_remove = []
        for index, exhausted_time in self._exhausted_keys.items():
            if exhausted_time < last_reset:
                keys_to_remove.append(index)
                logger.info(f"Key {self._keys[index].get('_name')} quota reset, available again")
        
        for index in keys_to_remove:
            del self._exhausted_keys[index]
    
    def reset_all(self):
        """Reset all keys (clear exhausted list)"""
        with self._lock:
            self._exhausted_keys.clear()
            self._current_index = 0
            logger.info("All keys reset")
    
    def get_status(self) -> dict:
        """Get status of all keys"""
        self._cleanup_exhausted()
        
        status = []
        for i, key in enumerate(self._keys):
            status.append({
                'index': i,
                'name': key.get('_name', 'unknown'),
                'is_current': i == self._current_index,
                'is_exhausted': i in self._exhausted_keys,
                'exhausted_at': self._exhausted_keys.get(i, None)
            })
        
        return {
            'total_keys': len(self._keys),
            'available_keys': self.available_keys,
            'current_index': self._current_index,
            'current_name': self.current_key_name,
            'keys': status
        }
    
    def reload_keys(self):
        """Reload keys from disk"""
        self._load_all_keys()
        # Reset exhausted if keys changed
        self._exhausted_keys = {k: v for k, v in self._exhausted_keys.items() 
                                if k < len(self._keys)}


# Global instance
api_key_manager = APIKeyManager()
