"""
Main entry point for MTYoutubeAutoPost
"""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.config import config
from app.utils.logger import setup_logger


def main():
    """Main application entry point"""
    # Setup logging
    setup_logger()
    
    logger.info("=" * 50)
    logger.info(f"Starting {config.get('app.name')} v{config.get('app.version')}")
    logger.info("=" * 50)
    
    # Import here to ensure config is loaded first
    from app.models.database import db
    
    logger.info(f"Database: {config.db_path}")
    logger.info(f"Workers: {config.worker_count}")
    logger.info(f"Delay range: {config.delay_range[0]}-{config.delay_range[1]}s")
    
    # Launch UI
    from app.ui.main_window import run_app
    run_app()


if __name__ == "__main__":
    main()

