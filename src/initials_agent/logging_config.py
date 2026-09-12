import logging
import sys

from .config import get_settings


def setup_logging() -> logging.Logger:
    settings = get_settings()
    level = getattr(logging, settings.app.log_level.upper(), logging.INFO)
    
    logger = logging.getLogger("initials_agent")
    logger.setLevel(level)
    
    if not logger.handlers:
        # Ensure stdout handles utf-8
        if sys.stdout.encoding.lower() != 'utf-8':
            sys.stdout.reconfigure(encoding='utf-8')
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger
