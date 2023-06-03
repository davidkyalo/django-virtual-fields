import os
from pathlib import Path
from pprint import pprint
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.db import models as m
from django.db.models.functions import Concat
from django.utils import timezone

from examples.example_01.models import Person, Post
from examples.faker import Faker
from virtual_fields.fields import VirtualField

pytestmark = [
    pytest.mark.django_db(databases=[*settings.DATABASES]),
]


@pytest.fixture(name="person_fn")
def person_fn_fixture(ufaker: Faker):
    def new(qs=Person.objects.all(), /, *, data=None, **kw):
        return qs.create(
            **{
                "first_name": ufaker.first_name(),
                "last_name": ufaker.last_name(),
                "dob": ufaker.date_object(),
                "data": {
                    "city": ufaker.city(),
                    "height": ufaker.pyfloat(None, 3, True, 1, 3),
                    "weight": ufaker.pyint(40, 120, 5),
                    **(data or {}),
                },
                **kw,
            }
        )

    return new


@pytest.fixture(name="post_fn")
def post_fn_fixture(ufaker: Faker, person_fn):
    def new(qs=None, /, *, author=None, data=None, **kw):
        if qs is None:
            qs = Post.objects.all()
            if not any(k in kw for k in ("author", "author_id")):
                qs = (Person.objects.order_by().last() or person_fn()).posts

        return qs.create(
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
    log: "Logger",
    post_fn: type[Post],
):
    qs = _qs = Person.objects.all()
    obj_0, obj_1 = person_fn(), person_fn()
    qs = (
        qs
        # .defer("age")
        .exclude(full_name="abc.xyz").filter(age__gt=0)
    )
    # qs = qs.filter(age__gt=2, city="Nairobi", full_name="abc").order_by("age")
    sql = qs.query
    print(f"SQL:       --> {sql}")
    print(f"EXPLAINED: --> {qs.explain()}")

    # log.block(settings.DATABASE_VENDOR)
    # log.dump(f"{sql};")
    assert {*qs} == {obj_0, obj_1}


@pytest.fixture(name="log_file", scope="session")
def logfile_fixture(tox_env_name):
    en = tox_env_name and f"-{tox_env_name}" or ""
    dir = Path(os.getcwd()) / f".local"
    dir.exists() or os.mkdir(dir)
    return dir / f".~!dump{en}.sql"


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
