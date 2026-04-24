import threading

_data_version = 0
_version_lock = threading.Lock()

def bump_version():
    global _data_version
    with _version_lock:
        _data_version += 1

def get_version():
    return _data_version
