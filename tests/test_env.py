import os
import re
import sys
from pathlib import Path

import pytest as pyt


def test_coverage():
    assert True


@pyt.fixture(scope="session")
def tox_env_name():
    tox_env_dir = os.getenv("TOX_ENV_DIR")
    tox_env = os.getenv("TOX_ENV_NAME")

    if tox_env_dir and tox_env:
        if sys.executable.startswith(tox_env_dir):
            return tox_env


@pyt.fixture()
def skip_if_not_tox(tox_env_name):
    if not tox_env_name:
        pyt.skip(f"not a tox environment")


def test_check_django_version(skip_if_not_tox, tox_env_name: str):
    from django import VERSION

    v_map = {
        "dj3.2": [(3, 2), (4, 0)],
        "dj4.1": [(4, 1), (4, 2)],
        "dj4.2": [(4, 2), (5, 0)],
    }

    ver_name = re.search(r"(?:^|(?:.+-))(dj[\d\.]+)(?:(?:-.+)|$)", tox_env_name)
    ver_name = ver_name and ver_name.group(1)
    if not (vc := v_map.get(ver_name)):
        pyt.skip(f"environment {tox_env_name!r} is not 'Django' specific")

    lv, uv = vc
    assert lv <= VERSION < uv


def test_check_py_version(skip_if_not_tox, tox_env_name: str):
    VERSION = sys.version_info

    v_map = {"py3.10": [(3, 10), (3, 11)], "py3.11": [(3, 11), (3, 12)]}

    var_name = re.search(r"(?:^|(?:.+-))(py[\d\.]+)(?:(?:-.+)|$)", tox_env_name)
    var_name = var_name and var_name.group(1)
    if not (vc := v_map.get(var_name)):
        pyt.skip(f"environment {tox_env_name!r} is not 'Python' specific")

    lv, uv = vc
    assert lv <= VERSION < uv


def test_check_db_vendor(tox_env_name: str, settings):
    from tests.app import settings as mod_settings

    v_map = {"sqlite": "sqlite3", "pgsql": "postgresql", "mysql": "mysql"}
    aka = {"psycopg2": "pgsql", "psycopg3": "pgsql"}
    v_map["psycopg2"] = v_map["psycopg3"] = v_map["pgsql"]
    env_vendor, vendor = os.getenv("DATABASE_VENDOR"), None
    if tox_env_name:
        vendor = re.search(
            r"(?:^|(?:.+-))(sqlite|mysql|pgsql|psycopg[23])(?:(?:[-.].+)|$)",
            tox_env_name,
        )
        if vendor := vendor and vendor.group(1):
            vendor = aka.get(vendor, vendor)

    if not (vendor := vendor or env_vendor):
        pyt.skip(f"environment {tox_env_name!r} is `DB vendor` specific")

    assert settings.DATABASE_VENDOR == vendor == mod_settings.DATABASE_VENDOR
    engine: str = settings.DATABASES["default"]["ENGINE"]
    assert engine == mod_settings.DATABASES["default"]["ENGINE"]
    assert engine.rpartition(".")[-1] == v_map[vendor]
