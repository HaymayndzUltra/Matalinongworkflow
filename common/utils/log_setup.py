#!/usr/bin/env python3
"""
Standardized Logging Configuration for Main-PC System

This module provides the canonical configure_logging function that should be used
to replace all logging.basicConfig calls throughout the Main-PC codebase.

Usage:
    from common.utils.log_setup import configure_logging
    logger = configure_logging(__name__)
"""

import logging
import sys
import os
from pathlib import Path
from typing import Optional, Union


def configure_logging(
    name: str,
    level: Union[str, int] = "INFO",
    format_str: Optional[str] = None,
    log_to_file: bool = False,
    log_dir: Optional[Path] = None
) -> logging.Logger:
    """
    Configure standardized logging for Main-PC agents.
    
    This function replaces logging.basicConfig and provides consistent
    logging configuration across all Main-PC services.
    
    Args:
        name: Logger name (usually __name__)
        level: Logging level (INFO, DEBUG, WARNING, ERROR)
        format_str: Custom format string (uses default if None)
        log_to_file: Whether to also log to a file
        log_dir: Directory for log files (defaults to /workspace/logs)
        
    Returns:
        Configured logger instance
    """
    # Convert string level to logging constant
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    
    # Default format following Main-PC standards
    if format_str is None:
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Create logger
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger
        
    logger.setLevel(level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(format_str)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if requested
    if log_to_file:
        if log_dir is None:
            # Use project logs directory instead of /workspace/logs
            import os
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            log_dir = Path(project_root) / "logs"
        
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"{name.replace('.', '_')}.log"
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(format_str)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False
    
    return logger


def get_mainpc_logger(agent_name: str) -> logging.Logger:
    """
    Convenience function to get a standardized Main-PC logger.
    
    Args:
        agent_name: Name of the agent (e.g., "ServiceRegistry")
        
    Returns:
        Configured logger with Main-PC standards
    """
    log_level = os.getenv("LOG_LEVEL", "INFO")
    return configure_logging(
        name=f"MainPC.{agent_name}",
        level=log_level,
        log_to_file=True
    )