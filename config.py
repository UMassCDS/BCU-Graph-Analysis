import os

UNITY_PATH = '/work/pi_plunkett_umass_edu/bcu/data'

LOCAL_PATH = './data'

if os.path.exists(UNITY_PATH):
    DATA_FOLDER = UNITY_PATH
    print(f"Unity cluster detected. Using data path: {DATA_FOLDER}")
else:
    DATA_FOLDER = LOCAL_PATH
    print(f"Local environment detected. Using data path: {DATA_FOLDER}")
RAW_OSM_DIR = os.path.join(DATA_FOLDER, 'raw', 'osm')
PROCESSED_OSM_DIR = os.path.join(DATA_FOLDER, 'processed', 'osm')
PARAMETERS_DIR = os.path.join(DATA_FOLDER, 'parameters')
