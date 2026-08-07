"""
Simple jobs.db backup: copies the SQLite file with a timestamp.
Usage: python -m scripts.backup_db
"""
import os
import shutil
from datetime import datetime

DB_PATH = os.getenv("JOBS_DB_PATH", "jobs.db")
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")


def backup():
    if not os.path.exists(DB_PATH):
        print(f"No database found at {DB_PATH} -- nothing to back up.")
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(BACKUP_DIR, f"jobs_{timestamp}.db")
    shutil.copy2(DB_PATH, dest)
    print(f"Backed up {DB_PATH} -> {dest}")
    return dest


if __name__ == "__main__":
    backup()
