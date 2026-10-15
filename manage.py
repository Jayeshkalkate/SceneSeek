#!/usr/bin/env python
"""Convenience wrapper so ``python manage.py ...`` also works from the repository root."""
import os
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent / "apps" / "api"
sys.path.insert(0, str(API_DIR))
os.chdir(API_DIR)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sceneseek_project.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
