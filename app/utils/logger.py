"""
Logger utility using Loguru
"""

import sys
from pathlib import Path
from loguru import logger

from app.config import config, LOGS_DIR


def setup_logger():
    """Configure loguru logger with settings from config"""
    
    # Remove default handler
    logger.remove()
    
    # Get settings
    log_level = config.get('logging.level', 'INFO')
    log_format = config.get('logging.format', '{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}')
    rotation = config.get('logging.rotation', '10 MB')
    retention = config.get('logging.retention', '7 days')
    
    # Console handler
    logger.add(
        sys.stdout,
        format=log_format,
        level=log_level,
        colorize=True
    )
    
    # File handler
    log_file = LOGS_DIR / "app_{time:YYYY-MM-DD}.log"
    logger.add(
        str(log_file),
        format=log_format,
        level=log_level,
        rotation=rotation,
        retention=retention,
        encoding='utf-8'
    )
    
    logger.info(f"Logger initialized - Level: {log_level}")
    return logger


# Initialize on import
setup_logger()
