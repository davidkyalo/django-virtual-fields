import os
import typing as t
from collections import defaultdict
from logging import getLogger

import pytest as pyt

from examples import faker
from tests import get_tox_env_name

if t.TYPE_CHECKING:
    from django.db import models as m

logger = getLogger(__name__)


@pyt.fixture(scope="session")
def tox_env_name():
    return get_tox_env_name()


@pyt.fixture(scope="session", autouse=True)
def _session_faker():
    fake = faker.faker
    fake.seed_instance(seed=0)
    fake.unique.clear()
    return fake


@pyt.fixture()
def ufaker(faker):
    return faker.unique


@pyt.fixture()
def factories():
    from tests.app.fields import FIELD_FACTORIES

    return FIELD_FACTORIES


@pyt.fixture(name="vendor", scope="session")
def vendor_fixture():
    from django.conf import settings

    return settings.DATABASE_VENDOR


@pyt.fixture(name="using")
def using_fixture(vendor):
    from django.conf import settings

    if vendor in settings.DATABASES:
        return vendor
    elif vendor == settings.DATABASE_VENDOR:
        return "default"

    pyt.skip(f"Database {vendor!r} not enabled.")


#

"""  
Coverage analysis 
"""

_covers = defaultdict[str, set[str]](set[str])
_covered = defaultdict(lambda: defaultdict(set))
_cov_marker_tests = set()


@pyt.fixture(scope="session")
def implementations():
    # from tests.app.fields import get_field_data_type
    from tests.app.models import ExprSource, FieldModel

    meta = FieldModel._meta
    iall = {*ExprSource}
    nojson = iall - {ExprSource.JSON}

    return {
        fld.__class__: {*iall}
        # if issubclass(get_field_data_type(fld.__class__) or object, JsonPrimitive)
        # else {*nojson}
        for fld in [*meta.fields]
    }


@pyt.fixture(scope="session", autouse=True)
def coverage_tasks(
    implementations: dict[type["m.Field"], set[str]], request: pyt.FixtureRequest
):
    from tests.app.models import TestModel

    tasks = {
        (test, cov, impl)
        for test, covs in _covers.items()
        for impl, req in implementations.items()
        for cov in req & covs
    }
    orig = len(tasks)
    # try:
    yield tasks
    # finally:

    rem = len(tasks)

    for test, spec, impl in sorted(
        tasks, key=lambda v: (*v[:-1], TestModel.get_field_name(v[-1]))
    ):
        logger.error(
            f"{test}[{str(spec)!r}] '{impl.__module__}::{impl.__qualname__}' not covered"
        )

    if request.session.testsfailed and not _cov_marker_tests:
        return

    # del tasks, implementations
    # assert rem == 0, f"{rem}/{orig}  ({round(rem/orig*100, 2)}%) tasks were not covered"


def node_key(item: pyt.Item):
    return item.nodeid.replace(item.name, item.f)


def pytest_collection_modifyitems(config, items: list[pyt.Function]):
    from tests.app.models import ExprSource

    for i in range(len(items)):
        item = items[i]
        key = item.function.__name__
        if mk := item.get_closest_marker("field_cov"):
            key = item.function.__name__
            _covers[key].update(mk.args or ExprSource)
            item.add_marker(pyt.mark.covered_test(key))
    items.sort(
        key=lambda it: "test_coverage" == it.function.__name__
        and (_cov_marker_tests.add(it.nodeid) or True)
    )


@pyt.fixture(autouse=True)
def _check_covers(request: pyt.FixtureRequest, coverage_tasks: set):
    if mk := request.node.get_closest_marker("covered_test"):
        test = mk.args[0]
        if all(f in request.fixturenames for f in ("field", "source")):
            field = request.getfixturevalue("field")
            source = request.getfixturevalue("source")
            coverage_tasks.discard((test, source, field))
