import typing as t
from logging import getLogger
from pathlib import Path

import pytest

if t.TYPE_CHECKING:
    from examples.faker import Faker


logger = getLogger(__name__)

from django.test import TestCase

TestCase.databases = "__all__"

# def pytest_configure(config: pytest.Config):
#     nl = "\n  - "
#     keys = "file_or_dir", "rootdir"
#     p_cwd, p_root, opt = Path(os.getcwd()), config.rootpath, config.option
#     p_example = p_root / "examples"
#     logger.error(
#         f"{nl.join(['', *filter(lambda n: n[:1] != '_', dir(config.option))])}"
#     )
#     logger.error(
#         f"{nl.join(['', f'{config.rootpath = }', f'{os.getcwd() = }', *(f'{k:24}: {getattr(opt, k)}' for k in keys )])}"
#     )
#     if paths := opt.file_or_dir:
#         for p in map(Path, paths):
#             if not (p if p.is_absolute() else p_cwd / p).is_relative_to(p_example):
#                 break
#         else:
#             os.environ["DJANGO_SETTINGS_MODULE"] = f"examples.settings"


# @pytest.fixture(scope="session", autouse=True)
# def faker_seed():
#     return 12345


@pytest.fixture(scope="session", autouse=True)
def _session_faker(_session_faker: "Faker"):
    from examples.faker import ExtraProvider

    _session_faker.add_provider(ExtraProvider)
    return _session_faker


@pytest.fixture()
def faker(faker: "Faker", _session_faker):
    from examples.faker import ExtraProvider

    faker is _session_faker or faker.add_provider(ExtraProvider)
    return faker


@pytest.fixture()
def ufaker(faker: "Faker"):
    return faker.unique
