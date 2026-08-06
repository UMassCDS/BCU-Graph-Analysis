import os
from pathlib import Path

DATA_FOLDER = Path(
    os.environ.get(
        "BCU_DATA_ROOT",
        "./data",
    )
)

print(f"Using data path: {DATA_FOLDER}")


RAW_OSM_DIR = Path(DATA_FOLDER) / 'raw' / 'osm'
PROCESSED_OSM_DIR = Path(DATA_FOLDER) / 'processed' / 'osm'
PARAMETERS_DIR = Path(__file__).resolve().parent / 'src' / 'bcu_analysis' / 'parameters'

NO_ACCESS_WEIGHT = 100.0
PROFILES_TO_APPLY = [
    ("child", "Baseline"),
    ("low_confidence_adult", "Baseline"),
    ("typical_adult", "Baseline")
]
