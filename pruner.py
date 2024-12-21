# File: /sweriko-pompv1/pruner.py

import os
import time
import logging
from pathlib import Path
import sys

# Configuration - Hardcoded as per user instruction
BUNDLE_IMAGES_DIR = Path("bundleimagesmain")
FRONTEND_COINS_DIR = Path("frontend/coins")
PRUNE_AGE_SECONDS = 200  # 4 minutes
CHECK_INTERVAL_SECONDS = 30  # 1 minute

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pruner.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def get_file_age_seconds(file_path):
    """
    Returns the age of the file or directory in seconds.

    Args:
        file_path (Path): The path to the file or directory.

    Returns:
        float: Age in seconds, or None if an error occurs.
    """
    try:
        file_mtime = file_path.stat().st_mtime
        current_time = time.time()
        return current_time - file_mtime
    except Exception as e:
        logging.error(f"Error getting modification time for {file_path}: {e}")
        return None

def delete_file(file_path):
    """
    Deletes a file and logs the action.

    Args:
        file_path (Path): The path to the file.
    """
    try:
        file_path.unlink()
        logging.info(f"Deleted file: {file_path}")
    except Exception as e:
        logging.error(f"Failed to delete file {file_path}: {e}")

def delete_directory(dir_path):
    """
    Deletes a directory and all its contents, then logs the action.

    Args:
        dir_path (Path): The path to the directory.
    """
    try:
        # Remove all files and subdirectories
        for child in dir_path.iterdir():
            if child.is_file():
                delete_file(child)
            elif child.is_dir():
                delete_directory(child)
        # Remove the now-empty directory
        dir_path.rmdir()
        logging.info(f"Deleted directory: {dir_path}")
    except Exception as e:
        logging.error(f"Failed to delete directory {dir_path}: {e}")

def prune_directories():
    """
    Prunes old PNGs and coin directories based on the age threshold.
    """
    age_threshold = PRUNE_AGE_SECONDS  # 4 minutes
    logging.info(f"Starting pruning process. Files older than {age_threshold} seconds will be deleted.")

    # Prune bundleimagesmain/*.png
    if BUNDLE_IMAGES_DIR.exists() and BUNDLE_IMAGES_DIR.is_dir():
        for png_file in BUNDLE_IMAGES_DIR.glob("*.png"):
            age = get_file_age_seconds(png_file)
            if age is not None and age > age_threshold:
                delete_file(png_file)
    else:
        logging.warning(f"Directory '{BUNDLE_IMAGES_DIR}' does not exist or is not a directory.")

    # Prune frontend/coins/<bundle_id>/ directories
    if FRONTEND_COINS_DIR.exists() and FRONTEND_COINS_DIR.is_dir():
        for bundle_dir in FRONTEND_COINS_DIR.iterdir():
            if bundle_dir.is_dir():
                # Check the age based on the directory's modification time
                age = get_file_age_seconds(bundle_dir)
                if age is not None and age > age_threshold:
                    delete_directory(bundle_dir)
    else:
        logging.warning(f"Directory '{FRONTEND_COINS_DIR}' does not exist or is not a directory.")

    logging.info("Pruning process completed.")

def main():
    """
    Main function to run the pruning process continuously.
    """
    logging.info("Pruner script started.")
    try:
        while True:
            prune_directories()
            logging.info(f"Sleeping for {CHECK_INTERVAL_SECONDS} seconds before next check.")
            time.sleep(CHECK_INTERVAL_SECONDS)  # Sleep for the specified interval
    except KeyboardInterrupt:
        logging.info("Pruner script terminated by user.")
    except Exception as e:
        logging.error(f"Unexpected error in pruning script: {e}", exc_info=True)

if __name__ == "__main__":
    main()
