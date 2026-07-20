import os
from pathlib import Path

UNITY_PATH = '/work/pi_plunkett_umass_edu/bcu/data'
LOCAL_PATH = './data'

if os.path.exists(UNITY_PATH):
    DATA_FOLDER = UNITY_PATH
    print(f"Unity cluster detected. Using data path: {DATA_FOLDER}")
else:
    DATA_FOLDER = LOCAL_PATH
    print(f"Local environment detected. Using data path: {DATA_FOLDER}")


RAW_OSM_DIR = Path(DATA_FOLDER) / 'raw' / 'osm'
PROCESSED_OSM_DIR = Path(DATA_FOLDER) / 'processed' / 'osm'
PARAMETERS_DIR = Path(DATA_FOLDER) / 'parameters'

NO_ACCESS_WEIGHT = 100.0
PROFILES_TO_APPLY = [
    ("child", "Baseline"),
    ("low_confidence_adult", "Baseline"),
    ("typical_adult", "Baseline")
]
