"""Paths and constants shared by the whole package."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
"""Repository root (``src/mbn/config.py`` -> two levels up from ``src``)."""

DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"
TEMPLATES_DIR = SITE_DIR / "templates"
ASSETS_DIR = SITE_DIR / "assets"
DATA_FILE = DATA_DIR / "morocco_by_the_numbers.json"
STATE_FILE = DATA_DIR / "sources_state.json"
WATCH_FILE = DATA_DIR / "datasets.txt"

DEFAULT_DATASETS = Path(os.environ.get("MBN_DATASETS", ROOT / "datasets"))
"""Where raw portal files live: one folder per publisher, then one per dataset."""

CKAN_API = "https://data.gov.ma/data/api/3/action"
DATASET_URL = "https://data.gov.ma/data/fr/dataset/"
USER_AGENT = "open-data-sync/1.0"
REPO_URL = "https://github.com/titiabdelghafour8-lab/morocco-by-the-numbers"
