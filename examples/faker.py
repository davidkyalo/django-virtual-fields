import json
import typing as t
from decimal import Decimal
import faker
from faker.providers import BaseProvider
from typing_extensions import Self

from faker.generator import Generator
from faker.providers import (
    address,
    bank,
    date_time,
    file,
    internet,
    lorem,
    misc,
    person,
    python,
)

TProvider = (
    python.Provider
    | lorem.Provider
    | date_time.Provider
    | internet.Provider
    | file.Provider
    | misc.Provider
    | address.Provider
    | person.Provider
    | bank.Provider
)

_JSONABLE_TYPES = bool, str, int, float, dict, tuple, list


class _JsonDict(dict):
    def __hash__(self) -> int:
        return hash((_JsonDict, json.dumps(self, sort_keys=True)))


class ExtraProvider(BaseProvider):
    generator: "Generator | Self | TProvider"

    def pybytes(self, min_len: int = 0, max_len: int = 1024) -> bytes:
        ln = self.random_int(min_len, max_len)
        return self.generator.binary(ln)

    @t.overload
    def fixed_decimal(
        self,
        decimal_places: int = 6,
        left_digits=None,
        positive=False,
        min_value=None,
        max_value=None,
    ) -> Decimal:
        ...

    def fixed_decimal(self, decimal_places=6, right_digits=None, *a, **kw) -> Decimal:
        if right_digits is None:
            right_digits = self.random_int(2, 54)
        return self.generator.pydecimal(right_digits, decimal_places, *a, **kw)

    def memoryview(self, min_len: int = 0, max_len: int = 1024):
        ln = self.random_int(min_len, max_len)
        return memoryview(self.generator.binary(ln))

    def json_dict(self, nb_elements=16, value_types=_JSONABLE_TYPES, **kw):
        val = self.generator.pydict(
            nb_elements=nb_elements, value_types=value_types, **kw
        )
        return _JsonDict(json.loads(json.dumps(val, default=str, skipkeys=True)))

    def rand_timedelta(self, end_datetime=None):
        g = self.generator
        return g.time_delta(g.date_time() if end_datetime is None else end_datetime)


Faker = Generator | ExtraProvider | TProvider

fake: Faker = faker.Faker()

fake.add_provider(ExtraProvider)


ufake: Faker = fake.unique
