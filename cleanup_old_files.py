#!/usr/bin/env python3
"""
Cleanup script for removing old temporary files and directories.
This should be run periodically as a cron job to prevent disk space issues.
"""

import os
import time
import logging
import tempfile
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def cleanup_old_files(max_age_hours=24):
    """
    Remove temporary files and directories older than max_age_hours.
    
    Args:
        max_age_hours (int): Maximum age of files to keep in hours
    """
    try:
        base_temp_dir = os.path.join(tempfile.gettempdir(), 'darkhole_temp')
        
        if not os.path.exists(base_temp_dir):
            logger.info("No temporary directory found, nothing to cleanup")
            return
            
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        cleaned_files = 0
        cleaned_dirs = 0
        
        # Walk through all session directories
        for session_dir in Path(base_temp_dir).iterdir():
            if session_dir.is_dir():
                try:
                    # Check directory age
                    dir_age = current_time - session_dir.stat().st_mtime
                    
                    if dir_age > max_age_seconds:
                        # Remove entire session directory
                        shutil.rmtree(session_dir)
                        cleaned_dirs += 1
                        logger.info(f"Removed old session directory: {session_dir.name}")
                    else:
                        # Check individual files in the directory
                        for file_path in session_dir.iterdir():
                            if file_path.is_file():
                                file_age = current_time - file_path.stat().st_mtime
                                if file_age > max_age_seconds:
                                    file_path.unlink()
                                    cleaned_files += 1
                                    logger.info(f"Removed old file: {file_path.name}")
                        
                        # Remove directory if empty
                        try:
                            session_dir.rmdir()
                            cleaned_dirs += 1
                            logger.info(f"Removed empty session directory: {session_dir.name}")
                        except OSError:
                            # Directory not empty, that's fine
                            pass
                            
                except Exception as e:
                    logger.error(f"Error processing {session_dir}: {str(e)}")
                    continue
        
        logger.info(f"Cleanup completed: {cleaned_files} files and {cleaned_dirs} directories removed")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")

if __name__ == "__main__":
    # Default cleanup of files older than 24 hours
    cleanup_old_files(24)