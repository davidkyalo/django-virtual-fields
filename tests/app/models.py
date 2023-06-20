import datetime
import typing as t
from base64 import b64encode
from collections import abc, defaultdict
from decimal import Decimal
from enum import auto
from operator import attrgetter
from types import GenericAlias, SimpleNamespace
from uuid import UUID

from django.core.exceptions import FieldDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models as m
from typing_extensions import Self

from examples.faker import ufaker
from tests.app.fields import get_field_data_type, to_field_name
from virtual_fields import VirtualField

from .utils import JsonPrimitive

_FT = t.TypeVar("_FT", bound=m.Field)
_T = t.TypeVar("_T")
_DT = t.TypeVar("_DT")

_notset = object()


T_Func = abc.Callable[..., _T]


class ExprSource(m.TextChoices):
    NONE = "N/A"
    FIELD = auto()
    EVAL = auto()
    JSON = auto()

    def _missing_(cls, val):
        return cls.NONE if val in (None, "") else val


class JSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, (memoryview, bytes)):
            return b64encode(o).decode("ascii")
        elif isinstance(o, UUID):
            return o.hex
        return super().default(o)


class AbcTestModel(m.Model):
    class Meta:
        abstract = True


class FieldModel(AbcTestModel):
    class Meta:
        abstract = True

    # bool types
    booleanfield: bool = m.BooleanField(blank=True, null=True)
    # str
    textfield: str = m.TextField(blank=True, null=True)
    charfield: str = m.CharField(max_length=255, blank=True, null=True)
    emailfield: str = m.EmailField(blank=True, null=True)
    slugfield: str = m.SlugField(blank=True, null=True)
    urlfield: str = m.URLField(blank=True, null=True)
    filefield: str = m.FileField(blank=True, null=True)
    filepathfield: str = m.FilePathField(blank=True, null=True)
    # imagefield: str = m.ImageField(blank=True, null=True)

    # number types
    decimalfield: Decimal = m.DecimalField(
        blank=True, null=True, decimal_places=4, max_digits=14
    )
    floatfield: float = m.FloatField(blank=True, null=True)
    bigintegerfield: int = m.BigIntegerField(blank=True, null=True)
    integerfield: int = m.IntegerField(blank=True, null=True)
    positivebigintegerfield: int = m.PositiveBigIntegerField(blank=True, null=True)
    smallintegerfield: int = m.SmallIntegerField(blank=True, null=True)
    positivesmallintegerfield: int = m.PositiveSmallIntegerField(blank=True, null=True)
    positiveintegerfield: int = m.PositiveIntegerField(blank=True, null=True)
    # date types
    datefield: datetime.date = m.DateField(blank=True, null=True)
    datetimefield: datetime.datetime = m.DateTimeField(blank=True, null=True)
    durationfield: datetime.timedelta = m.DurationField(blank=True, null=True)
    timefield: datetime.time = m.TimeField(blank=True, null=True)

    # Other types
    binaryfield: memoryview = m.BinaryField(blank=True, null=True)
    uuidfield: UUID = m.UUIDField(blank=True, null=True)
    genericipaddressfield: str = m.GenericIPAddressField(blank=True, null=True)

    # json
    jsonfield: JsonPrimitive = m.JSONField(blank=True, null=True)
    _rel = dict(to="self", on_delete=m.SET_NULL, blank=True, null=True)
    foreignkey = m.ForeignKey(**_rel, related_name="foreignkey_reverse")
    onetoonefield = m.OneToOneField(**_rel, related_name="onetoonefield_reverse")
    manytomanyfield = m.ManyToManyField("self", blank=True)
    del _rel
    foreignkey_reverse: "m.manager.RelatedManager[Self]"
    onetoonefield_reverse: Self | None

    json: dict = m.JSONField(default=dict, encoder=JSONEncoder, blank=True, null=True)


class PsuedoFieldModel(AbcTestModel):
    class Meta:
        abstract = True


class TestModel(FieldModel):
    __class_getitem__ = classmethod(GenericAlias)

    class Meta:
        verbose_name = "Field Implementation"
        base_manager_name = "objects"
        default_manager_name = "objects"

    objects = m.Manager[Self]()

    NONE = ExprSource.NONE
    FIELD = ExprSource.FIELD
    EVAL = ExprSource.EVAL
    JSON = ExprSource.JSON

    test: _T
    proxy: _T
    field_name: t.ClassVar[str]
    source: t.ClassVar[ExprSource]
    field_type: t.ClassVar[type[m.Field]]

    proxy_value = property(attrgetter("test"))

    implemented: t.Final[dict[type[m.Field], set]] = defaultdict(set)

    def __init_subclass__(cls, **kw):
        super.__init_subclass__(**kw)
        dct = cls.__dict__
        cls.field_type = tt = dct.get("field_type") or None
        cls.field_name = dct.get("field_name") or (tt and tt.__name__.lower())
        cls.source = dct.get("source")
        cls.proxy = dct.get("proxy") or cls.proxy_value

    @classmethod
    def get_field(cls, name: str | type, default: _DT = _notset) -> m.Field | _DT:
        name = to_field_name(name)
        try:
            return cls._meta.get_field(name)
        except FieldDoesNotExist:
            if default is _notset:
                raise
            return default

    @classmethod
    def get_coverage(cls, name: str | type, default: _DT = _notset) -> m.Field | _DT:
        name = to_field_name(name)
        try:
            return cls._meta.get_field(name)
        except FieldDoesNotExist:
            if default is _notset:
                raise
            return default

    @classmethod
    def get_field_name(cls, name: str | type[_FT], default: _DT = _notset) -> type[_FT]:
        if default is not _notset:
            default = SimpleNamespace(attname=default)
        return cls.get_field(name, default).name

    @property
    def field_value(self) -> _T:
        return getattr(self, self.field_name)

    @field_value.setter
    def field_value(self, val: _T):
        setattr(self, self.field_name, val)

    @property
    def json_value(self) -> _T:
        if self.source is self.JSON:
            val = self.json[self.field_name]
            typ = get_field_data_type(self.field_type)

            if not isinstance(val, typ) and not issubclass(typ, JsonPrimitive):
                val = self._meta.get_field(self.field_name).to_python(val)
            return val

    @json_value.setter
    def json_value(self, val):
        if self.source is self.JSON:
            self.json[self.field_name] = val

    @property
    def value(self) -> _T:
        return self.json_value if self.source is self.JSON else self.field_value

    @value.setter
    def value(self, val: _T):
        self.field_value = self.json_value = val

    @t.overload
    @classmethod
    def define(
        cls,
        /,
        test: type[VirtualField] = None,
        *,
        name: str = None,
        field_type: type[m.Field] = None,
        source: ExprSource = None,
        **dct,
    ) -> type[Self]:
        ...

    @classmethod
    def define(cls, /, *, name=None, **dct) -> type[Self]:
        if "Meta" not in dct:
            dct["Meta"] = type("Meta", (ProxyMeta,), {})
        elif isinstance(dct["Meta"], abc.Mapping):
            dct["Meta"] = type("Meta", (ProxyMeta,), dict(dct["Meta"]))

        field_type = dct.get("field_type")
        if name is None:
            name = f"TestCase_{(field_type or  m.Field).__name__}_{ufaker.random_int(100, 999)}"

        dct = {
            "__module__": __name__,
            "__name__": name,
            "proxy": VirtualField("test", defer=True)
            if isinstance(dct.get("test"), m.Field)
            else None,
            **dct,
            "source": ExprSource(dct.get("source")),
        }
        return type(name, (cls,), dct)

    def __str__(self) -> str:
        target = self.field_type and self.field_type.__name__.lower() or ""
        return f"{target} - {repr(getattr(self, 'test', ''))[:60]}({self.pk})".strip(
            " -"
        )


class ProxyMeta:
    def __init_subclass__(cls) -> None:
        cls.proxy = cls.__dict__.get("proxy", True)
        cls.app_label = cls.__dict__.get("app_label", "app")
