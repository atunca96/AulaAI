import os
import threading

VERSION_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "version.txt")

def bump_version():
    try:
        v = get_version()
        os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
        with open(VERSION_FILE, "w") as f:
            f.write(str(v + 1))
    except:
        pass

def get_version():
    if not os.path.exists(VERSION_FILE):
        return 0
    try:
        with open(VERSION_FILE, "r") as f:
            return int(f.read().strip())
    except:
        return 0
