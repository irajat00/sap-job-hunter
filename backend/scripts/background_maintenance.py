"""
Standalone entry point for scheduled maintenance-only runs (no new job
collection) -- for a cron/Task Scheduler entry separate from the main
collector, e.g. every 6 hours, while the main collector runs every 15
min. Reuses collectors/self_maintain.py, nothing new.

Usage: python -m scripts.background_maintenance
"""
from collectors.self_maintain import run_self_maintenance

if __name__ == "__main__":
    run_self_maintenance()
