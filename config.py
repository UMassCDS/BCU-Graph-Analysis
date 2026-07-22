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
