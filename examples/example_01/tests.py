import os
from pathlib import Path
from pprint import pprint
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.utils import timezone

from examples.example_01.models import Person, Post
from examples.faker import Faker
from virtual_fields.fields import VirtualField

pytestmark = [
    pytest.mark.django_db,
]


@pytest.fixture(name="person_fn")
def person_fn_fixture(ufaker: Faker, using):
    def new(qs=Person.objects.all(), /, *, data=None, **kw):
        return qs.using(using).create(
            **{
                "first_name": ufaker.first_name(),
                "last_name": ufaker.last_name(),
                "dob": ufaker.date_object(),
                "data": {
                    "city": ufaker.city(),
                    "height": ufaker.pyfloat(None, 3, True, 1, 3),
                    # "height": ufaker.pydecimal(None, 3, True, 1, 3),
                    "weight": ufaker.pyint(40, 120, 5),
                    **(data or {}),
                },
                **kw,
            }
        )

    return new


@pytest.fixture(name="vendor", scope="session", params=["sqlite", "mysql", "pgsql"])
def vendor_fixture(request: pytest.FixtureRequest):
    if (val := request.param) in settings.DATABASES_BY_VENDOR:
        return val
    pytest.skip(f"Database {val!r} not available")


@pytest.fixture(name="using")
def using_fixture(vendor):
    if vendor in settings.DATABASES:
        return vendor
    elif vendor == settings.DATABASE_VENDOR:
        return "default"

    pytest.skip(f"Database {vendor!r} not enabled.")


@pytest.fixture(name="log_file", scope="session")
def logfile_fixture():
    return Path(os.getcwd()) / ".~!dump.sql"


@pytest.fixture(name="log_io", scope="session")
def log_io_fixture(log_file: Path):
    with log_file.open("w+") as fo:
        yield fo


@pytest.fixture(name="log", scope="session")
def log_fixture(log_io: Path, vendor: str):
    log = Logger(kwds=dict(file=log_io))
    log.block(
        vendor.upper(),
        *(
            v
            for f in Person._meta.get_fields()
            if isinstance(f, VirtualField) and (c := str(f.cached_col))
            for v in (
                f"{f.name!r}",
                *(
                    f"  {c[x * 120 : x * 120 + 120]}"
                    for x in range(int(len(c) / 120) + 1)
                ),
                "",
            )
        ),
    )
    return log


@pytest.fixture(name="post_fn")
def post_fn_fixture(ufaker: Faker, using, person_fn):
    def new(qs=None, /, *, author=None, data=None, **kw):
        if qs is None:
            qs = Post.objects.all()
            if not any(k in kw for k in ("author", "author_id")):
                qs = (
                    Person.objects.using(using).order_by().last() or person_fn()
                ).posts

        return qs.using(using).create(
            **{
                "title": ufaker.sentence(ufaker.random_int(3, 6))[:255],
                "content": "\n\n".join(
                    ufaker.paragraph(ufaker.random_int(3, 6))
                    for _ in range(ufaker.random_int(2, 10))
                ),
                "published_at": ufaker.date_time_this_year(),
                **kw,
            }
        )

    return new


def test_example(
    ufaker: Faker,
    person_fn: type[Person],
    using: str,
    vendor: str,
    log: "Logger",
    post_fn: type[Post],
):
    qs = _qs = Person.objects.using(using).all()
    person_fn(), person_fn()

    # qs = qs.filter(age__gt=2, city="Nairobi", full_name="abc").order_by("age")
    sql = _qs.query
    print(f"SQL: --> {sql}")

    log.block(vendor)
    log.dump(f"{sql};")

    pprint([*_qs], depth=9, indent=4)

    # assert 0


class Logger(SimpleNamespace):
    kwds: dict

    def now(self):
        return timezone.now().isoformat(" ", "seconds")

    def log(self, *a, time=None, end=" */\n", **kw):
        time = (
            ()
            if time in (False, "")
            else (f"[{self.now()}]",)
            if time in (None, True)
            else (time and f"[{time}]",)
        )
        return print("/**", *time, *a, end=end, **self.kwds | kw)

    __call__ = log

    def block(self, *a, sep="\n* ", end="\n**/\n", **kw):
        return self.log(*a, sep=sep, end=end, **kw)

    def dump(self, *a, end="\n", **kw):
        self.log()
        print(*a, end=end, **self.kwds | kw)
        self.log("end", time=False)
