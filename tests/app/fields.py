import datetime
import sys
import typing as t
from collections import defaultdict
from decimal import Decimal
from functools import partial
from uuid import UUID

from django.apps import apps
from django.db import models as m
from tests.faker import ufake
from virtual_fields.utils import JsonPrimitive


_FT = t.TypeVar("_FT", bound=m.Field)
_T = t.TypeVar("_T")

_notset = object()


FIELD_FACTORIES = {
    m.BooleanField: ufake.pybool,
    m.CharField: ufake.pystr,
    m.EmailField: ufake.email,
    m.SlugField: ufake.slug,
    m.TextField: ufake.text,
    m.URLField: ufake.url,
    m.BinaryField: ufake.memoryview,
    m.GenericIPAddressField: ufake.ipv6,
    m.DateField: ufake.date_object,
    m.DateTimeField: ufake.date_time,
    m.DurationField: ufake.rand_timedelta,
    m.TimeField: ufake.time_object,
    m.FilePathField: ufake.file_path,
    m.DecimalField: ufake.fixed_decimal,
    m.FloatField: ufake.pyfloat,
    m.IntegerField: ufake.pyint,
    m.BigIntegerField: partial(ufake.pyint, int(3e9), int(sys.maxsize * 0.7)),
    m.PositiveBigIntegerField: partial(ufake.pyint, int(3e9), int(sys.maxsize * 0.7)),
    m.SmallIntegerField: partial(ufake.pyint, 0, 9999),
    m.PositiveSmallIntegerField: partial(ufake.pyint, 0, 9999),
    m.PositiveIntegerField: ufake.pyint,
    m.UUIDField: partial(ufake.uuid4, cast_to=None),
    m.JSONField: ufake.json_dict,
    m.FileField: ufake.file_path,
    # m.ImageField: lambda:None,
    m.ForeignKey: lambda: None,
    m.OneToOneField: lambda: None,
    m.ManyToManyField: lambda: None,
}


FIELD_DATA_TYPES = {
    # bool
    m.BooleanField: bool,
    # str
    m.TextField: str,
    m.CharField: str,
    m.EmailField: str,
    m.SlugField: str,
    m.URLField: str,
    m.FileField: str,
    m.FilePathField: str,
    m.GenericIPAddressField: str,
    # m.ImageField: str,
    # bytes
    m.BinaryField: memoryview,
    # date types
    m.DateField: datetime.date,
    m.DateTimeField: datetime.datetime,
    m.DurationField: datetime.timedelta,
    m.TimeField: datetime.time,
    # number types
    m.DecimalField: Decimal,
    m.FloatField: float,
    m.BigIntegerField: int,
    m.IntegerField: int,
    m.PositiveBigIntegerField: int,
    m.SmallIntegerField: int,
    m.PositiveSmallIntegerField: int,
    m.PositiveIntegerField: int,
    # UUID
    m.UUIDField: UUID,
    # JSON
    m.JSONField: JsonPrimitive,
    # relation types
    m.ForeignKey: m.Model,
    m.OneToOneField: m.Model,
    m.ManyToManyField: m.QuerySet,
}

FIELD_TO_JSON_DEFAULTS = defaultdict(
    str,
    {
        m.BinaryField: m.BinaryField().value_to_string,
    },
)


def get_field_data_type(cls: type[_FT]) -> type[_T]:
    return FIELD_DATA_TYPES.get(cls)


def to_field_name(field: str | type[_FT]) -> type[_FT]:
    return (field.__name__ if isinstance(field, type) else field).lower()


_type_2_id_field_map = {}
_id_2_type_field_map = {}


def field_type_id(field: str | type[_FT]) -> str:
    if isinstance(field, str):
        return _type_2_id_field_map[_id_2_type_field_map[field]]
    elif field in _type_2_id_field_map:
        return _type_2_id_field_map[field]

    if app := apps.get_containing_app_config(field.__module__):
        id = f"{app.label}_{field.__name__.lower()}"
    else:
        id = f"{field.__name__.lower()}"

    if field is not _id_2_type_field_map.setdefault(id, field):
        raise TypeError(f"duplicate id {id=}")
    if id is not _type_2_id_field_map.setdefault(field, id):
        raise TypeError(f"multiple ids assigned {field=}")
    return id
