"""
Configuration Manager for MTYoutubeAutoPost
Centralized configuration loading and saving
"""

import json
from pathlib import Path
from typing import Any, Optional
from loguru import logger

# Base paths
# __file__ = app/config.py
# parent = app/
# parent.parent = MTYoutubeAutoPost/
APP_ROOT = Path(__file__).parent.parent  # D:\dev\MTYoutubeAutoPost
DATA_DIR = APP_ROOT / "data"
CONFIG_DIR = DATA_DIR / "config"
DB_DIR = DATA_DIR / "db"
LOGS_DIR = DATA_DIR / "logs"

# Config files
SETTINGS_FILE = CONFIG_DIR / "settings.json"
UI_STATE_FILE = CONFIG_DIR / "ui_state.json"
YOUTUBE_AUTH_FILE = CONFIG_DIR / "youtube_token.json"

# Ensure directories exist
for dir_path in [CONFIG_DIR, DB_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)


class ConfigManager:
    """
    Thread-safe configuration manager
    Handles loading and saving of all config files
    """
    
    _instance: Optional['ConfigManager'] = None
    _settings: dict = {}
    _ui_state: dict = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_all()
        return cls._instance
    
    def _load_all(self):
        """Load all configuration files"""
        self._settings = self._load_json(SETTINGS_FILE, self._get_default_settings())
        self._ui_state = self._load_json(UI_STATE_FILE, self._get_default_ui_state())
        logger.info("Configuration loaded successfully")
    
    def _load_json(self, path: Path, default: dict) -> dict:
        """Load JSON file with fallback to default"""
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # Create file with defaults
                self._save_json(path, default)
                return default
        except Exception as e:
            logger.error(f"Error loading {path}: {e}")
            return default
    
    def _save_json(self, path: Path, data: dict):
        """Save data to JSON file"""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving {path}: {e}")
    
    @staticmethod
    def _get_default_settings() -> dict:
        """Default settings"""
        return {
            "app": {
                "name": "MTYoutubeAutoPost",
                "version": "1.0.0",
                "language": "th"
            },
            "upload": {
                "worker_count": 2,
                "delay_from_ss": 30,
                "delay_to_ss": 120,
                "max_retries": 3,
                "default_privacy": "unlisted",
                "default_category_id": 22
            },
            "youtube": {
                "client_secrets_file": "client_secrets.json",
                "token_file": "youtube_token.json",
                "api_service_name": "youtube",
                "api_version": "v3",
                "scopes": [
                    "https://www.googleapis.com/auth/youtube.upload",
                    "https://www.googleapis.com/auth/youtube",
                    "https://www.googleapis.com/auth/youtube.force-ssl"
                ]
            },
            "database": {
                "path": "youtube_uploader.db"
            },
            "logging": {
                "level": "INFO",
                "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
                "rotation": "10 MB",
                "retention": "7 days"
            }
        }
    
    @staticmethod
    def _get_default_ui_state() -> dict:
        """Default UI state"""
        return {
            "window": {
                "width": 1200,
                "height": 800,
                "x": None,
                "y": None,
                "maximized": False
            },
            "last_folders": [],
            "splitter_sizes": [300, 900],
            "theme": "light"
        }
    
    # Settings getters/setters
    def get(self, key: str, default: Any = None) -> Any:
        """Get setting value using dot notation (e.g., 'upload.worker_count')"""
        keys = key.split('.')
        value = self._settings
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any):
        """Set setting value using dot notation"""
        keys = key.split('.')
        target = self._settings
        for k in keys[:-1]:
            target = target.setdefault(k, {})
        target[keys[-1]] = value
        self.save_settings()
    
    def save_settings(self):
        """Save current settings to file"""
        self._save_json(SETTINGS_FILE, self._settings)
        logger.debug("Settings saved")
    
    # UI State getters/setters
    def get_ui(self, key: str, default: Any = None) -> Any:
        """Get UI state value"""
        keys = key.split('.')
        value = self._ui_state
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_ui(self, key: str, value: Any):
        """Set UI state value"""
        keys = key.split('.')
        target = self._ui_state
        for k in keys[:-1]:
            target = target.setdefault(k, {})
        target[keys[-1]] = value
        self.save_ui_state()
    
    def save_ui_state(self):
        """Save current UI state to file"""
        self._save_json(UI_STATE_FILE, self._ui_state)
        logger.debug("UI state saved")
    
    # Convenience properties
    @property
    def worker_count(self) -> int:
        return self.get('upload.worker_count', 2)
    
    @worker_count.setter
    def worker_count(self, value: int):
        self.set('upload.worker_count', max(1, min(5, value)))
    
    @property
    def delay_range(self) -> tuple[int, int]:
        return (
            self.get('upload.delay_from_ss', 30),
            self.get('upload.delay_to_ss', 120)
        )
    
    @delay_range.setter
    def delay_range(self, value: tuple[int, int]):
        self.set('upload.delay_from_ss', value[0])
        self.set('upload.delay_to_ss', value[1])
    
    @property
    def max_retries(self) -> int:
        return self.get('upload.max_retries', 3)
    
    @property
    def db_path(self) -> Path:
        return DB_DIR / self.get('database.path', 'youtube_uploader.db')
    
    @property
    def youtube_scopes(self) -> list[str]:
        return self.get('youtube.scopes', [])
    
    @property
    def client_secrets_path(self) -> Path:
        return CONFIG_DIR / self.get('youtube.client_secrets_file', 'client_secrets.json')
    
    @property
    def youtube_token_path(self) -> Path:
        return CONFIG_DIR / self.get('youtube.token_file', 'youtube_token.json')


# Global instance
config = ConfigManager()
