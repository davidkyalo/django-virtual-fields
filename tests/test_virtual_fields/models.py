import datetime
import typing as t
from base64 import b64encode
from collections import abc, defaultdict
from copy import copy, deepcopy
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
from tests.test_virtual_fields.fields import get_field_data_type, to_field_name
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


class ProxyMeta:
    def __init_subclass__(cls) -> None:
        cls.proxy = cls.__dict__.get("proxy", True)
        cls.app_label = cls.__dict__.get("app_label", "test_virtual_fields")


class AbcTestModel(m.Model):
    __class_getitem__ = classmethod(GenericAlias)

    class Meta:
        abstract = True
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
    field_name_2: t.ClassVar[str]
    source: t.ClassVar[ExprSource]
    field_type: t.ClassVar[type[m.Field]]

    proxy_value = property(attrgetter("test"))

    implemented: t.Final[dict[type[m.Field], set]] = defaultdict(set)

    def __init_subclass__(cls, **kw):
        super.__init_subclass__(**kw)
        dct = cls.__dict__
        cls.field_type = tt = dct.get("field_type") or None
        cls.field_name = dct.get("field_name") or (tt and tt.__name__.lower())
        cls.field_name_2 = dct.get("field_name_2") or f"{cls.field_name}_2"
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
    def field_value_2(self) -> _T:
        return getattr(self, self.field_name_2)

    @field_value_2.setter
    def field_value_2(self, val: _T):
        setattr(self, self.field_name_2, val)

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
    def json_value_2(self) -> _T:
        if self.source is self.JSON:
            val = self.json[self.field_name_2]
            typ = get_field_data_type(self.field_type)

            if not isinstance(val, typ) and not issubclass(typ, JsonPrimitive):
                val = self._meta.get_field(self.field_name_2).to_python(val)
            return val

    @json_value_2.setter
    def json_value_2(self, val):
        if self.source is self.JSON:
            self.json[self.field_name_2] = val

    @property
    def value(self) -> _T:
        return self.json_value if self.source is self.JSON else self.field_value

    @value.setter
    def value(self, val: _T):
        self.field_value = self.json_value = val

    @property
    def value_2(self) -> _T:
        return self.json_value_2 if self.source is self.JSON else self.field_value_2

    @value_2.setter
    def value_2(self, val: _T):
        self.field_value_2 = self.json_value_2 = val

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
    def define(cls, *bases, name=None, **dct) -> type[Self]:
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
        return type(name, bases or (cls,), dct)

    def __str__(self) -> str:
        target = self.field_type and self.field_type.__name__.lower() or ""
        return f"{target} - {repr(getattr(self, 'test', ''))[:60]}({self.pk})".strip(
            " -"
        )


class AbcFieldModel(AbcTestModel):
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
    foreignkey = m.ForeignKey(
        **_rel, related_name="foreignkey_reverse", swappable=False
    )
    onetoonefield = m.OneToOneField(
        **_rel, related_name="onetoonefield_reverse", swappable=False
    )
    manytomanyfield = m.ManyToManyField("self", blank=True, swappable=False)
    del _rel
    foreignkey_reverse: "m.manager.RelatedManager[Self]"
    onetoonefield_reverse: Self | None

    json: dict = m.JSONField(default=dict, encoder=JSONEncoder, blank=True, null=True)
    v = n = n2 = v2 = None
    for n in [n for n, v in vars().items() if isinstance(v, m.Field)]:
        if (
            n[-2:] != "_2"
            and (n2 := f"{n}_2") not in vars()
            and isinstance(v := vars()[n], m.Field)
        ):
            print(f"coping {n!r:<30} --> {f'{n}_2'!r:<30}....")
            if isinstance(v, m.ForeignKey):
                args, kwargs = v.deconstruct()[-2:]
                kwargs["related_name"] = f"{kwargs['related_name']}_2"
                v2 = v.__class__(*args, **kwargs)
                del args, kwargs
            else:
                v2 = v.clone()
            vars().setdefault(n2, v2)

    del n2, n, v, v2


class FieldModel(AbcFieldModel):
    class Meta:
        verbose_name = "Field Implementation"

    alt: "m.manager.RelatedManager[AltFieldModel]"
    alt_many: "m.manager.ManyToManyRelatedManager[AltFieldModel]"
    alt_one: "AltFieldModel | None"


class AltFieldModel(AbcFieldModel):
    alt: "m.manager.RelatedManager[AltFieldModel]"
    alt_many: "m.manager.ManyToManyRelatedManager[AltFieldModel]"
    alt_one: "AltFieldModel | None"

    _rel = dict(to=FieldModel, on_delete=m.SET_NULL, blank=True, null=True)
    to = m.ForeignKey(**_rel, related_name="alt")
    to_one = m.OneToOneField(**_rel, related_name="alt_one")
    to_many = m.ManyToManyField(FieldModel, related_name="alt_many", blank=True)
    del _rel

    class Meta:
        verbose_name = "Alt-Field Implementation"


class TestModel(AbcFieldModel):
    class Meta:
        verbose_name = "test model"


class TestModel_A(AbcFieldModel):
    class Meta:
        verbose_name = "test model A"


class TestModel_B(AbcFieldModel):
    class Meta:
        verbose_name = "test model B"


class TestModel_C(AbcFieldModel):
    class Meta:
        verbose_name = "test model C"
