import os
import sys


def get_env_name(default="dev"):
    if not (val := os.getenv("ENV_NAME")):
        if val := get_tox_env_name():
            pass
    return val or default


def get_tox_env_name(default=None):
    tox_env, tox_env_dir = os.getenv("TOX_ENV_NAME"), os.getenv("TOX_ENV_DIR")
    prog, val = sys.executable, default
    if tox_env_dir and tox_env:
        if prog.startswith(tox_env_dir):
            val = tox_env

    return val
