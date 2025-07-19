"""
Logging service implementation
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from ..domain.configuration import LoggingConfig
from ..interfaces import ILogger


class LoggingService(ILogger):
    """Concrete implementation of logging service"""

    def __init__(self, config: LoggingConfig):
        self.config = config
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Setup the logger with configuration"""
        logger = logging.getLogger("provisioning")

        # Set level
        level = getattr(logging, self.config.level.upper(), logging.INFO)
        logger.setLevel(level)

        # Clear existing handlers
        logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Console handler
        if self.config.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        # File handler
        if self.config.file_path:
            try:
                # Ensure directory exists
                Path(self.config.file_path).parent.mkdir(parents=True, exist_ok=True)

                file_handler = logging.handlers.RotatingFileHandler(
                    self.config.file_path,
                    maxBytes=self.config.max_file_size,
                    backupCount=self.config.backup_count,
                )
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except Exception as e:
                # Use basic logging since file logging failed
            import logging
            logging.basicConfig(level=logging.WARNING)
            logging.warning(f"Could not setup file logging: {e}")

        return logger

    def debug(self, message: str, **kwargs) -> None:
        self.logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        self.logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        self.logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        self.logger.critical(message, **kwargs)
