import typing as t
from collections.abc import Iterable
from functools import reduce
from operator import eq, or_
from types import UnionType
from uuid import UUID

import pytest as pyt
from django.db import models as m
from django.db.models.fields.json import KT, JSONField
from django.db.models.query import QuerySet
from zana.types.collections import DefaultDict, ReadonlyDict

from tests.app.models import ExprSource as Src
from tests.app.models import T_Func, TestModel
from virtual_fields import VirtualField
from virtual_fields._util import _db_instance_qs
from virtual_fields.models import ImplementsVirtualFields

_VT = t.TypeVar("_VT", covariant=True)
_FT = t.TypeVar("_FT", bound=m.Field, covariant=True)
_MT = t.TypeVar("_MT", bound=TestModel, covariant=True)


_TF_Target = t.Literal["field", "json"]

pytestmark = [
    pyt.mark.django_db,
]


@pyt.fixture
def to_python(field):
    return TestModel.get_field(field, m.Field()).to_python


@pyt.fixture
def factory(factories, field):
    return factories[field]


@pyt.fixture
def field_name(field: type):
    return TestModel.get_field_name(field)


@pyt.fixture
def through():
    return ""


@pyt.fixture
def src_field_alias(through: str, source: Src):
    if through and source == Src.JSON:
        return "json_alias"


@pyt.fixture
def expression(
    field_name: str, through: str, field: m.Field, source: Src, src_field_alias
):
    prefix = f"{through}__".lstrip("_")
    match source:
        case Src.JSON:
            exp = f"{src_field_alias or f'{prefix}json'}__{field_name}"
            return exp if issubclass(field, JSONField) else KT(exp)
        case Src.EVAL:
            return m.Case(
                m.When(
                    m.Q(**{f"{prefix}{field_name}__isnull": False}),
                    then=m.F(f"{prefix}{field_name}"),
                ),
                default=m.Value(None),
            )
        case _:
            return f"{prefix}{field_name}"


@pyt.fixture
def type_var(source: Src, field):
    if source == Src.JSON:
        return field


@pyt.fixture
def cls(source: Src, field, type_var):
    return VirtualField[type_var] if type_var is not None else VirtualField


@pyt.fixture
def def_kwargs(src_field_alias, through: str, source: Src):
    if src_field_alias:
        kwds = {src_field_alias: VirtualField(f"{through}__json", defer=True)}
        return kwds
    return {}


@pyt.fixture
def define(source: Src, field, new, def_kwargs):
    def_kwargs = {"source": source, "field_type": field, **def_kwargs}

    def func(test=def_kwargs.pop("test", None), **kw):
        test = new() if test is None else test
        return TestModel.define(test=test, **def_kwargs | kw)

    return func


@pyt.fixture
def new(cls: type[VirtualField], expression, kwargs: dict):
    def func(expression=expression, **kw):
        return cls(expression, **kwargs | kw)

    return func


@pyt.fixture
def model(define: T_Func[type[m.Model]]):
    return define()


@pyt.fixture
def kwargs(request: pyt.FixtureRequest, field: type[m.Field], source):
    self: FieldTestCase = request.instance
    skw = getattr(self, f"{source!s}_source_kwargs".lower(), {})
    ftk = self.field_type_kwargs
    mro = field.__mro__[::-1]
    return {
        **self.default_kwargs,
        **reduce(or_, (ftk.get(b, {}) for b in mro), {}),
        **reduce(or_, (skw.get(b, {}) for b in mro), {}),
    }


def test_coverage():
    assert True


@pyt.mark.field_cov(Src.FIELD, Src.EVAL, Src.JSON)
class FieldTestCase(t.Generic[_VT, _FT, _MT]):
    field_types: t.ClassVar[tuple[type[_FT]]]
    data_type: t.ClassVar[type[_VT]]
    all_sources: t.ClassVar = (Src.FIELD, Src.EVAL, Src.JSON)
    source_support: t.ClassVar = DefaultDict[type[_FT], bool]((), True)
    fixture: pyt.FixtureRequest
    default_kwargs: dict = ReadonlyDict(defer=False)
    field_type_kwargs: dict = ReadonlyDict()
    json_source_kwargs: dict = ReadonlyDict()
    # field_source_kwargs: dict = ReadonlyDict()

    source: Src
    field: type[_FT]
    model: type[_MT]
    request: pyt.FixtureRequest

    def __init_subclass__(cls) -> None:
        if ob := cls.__orig_bases__:
            if args := ob[0].__args__:
                if "field_types" not in cls.__dict__:
                    if isinstance(arg := args[1], UnionType):
                        if all(
                            isinstance(a, type) and issubclass(a, m.Field)
                            for a in arg.__args__
                        ):
                            cls.field_types = tuple(arg.__args__)
                    elif isinstance(arg, type) and issubclass(arg, m.Field):
                        cls.field_types = (arg,)
                if "data_type" not in cls.__dict__:
                    if not isinstance(arg := args[0], t.TypeVar):
                        cls.data_type = arg

        if "field_fixture" not in cls.__dict__ and cls.field_types:

            @pyt.fixture(
                name="field",
                params=cls.field_types,
                ids=[f.__name__ for f in cls.field_types],
            )
            def field_fixture(self, request: pyt.FixtureRequest):
                return request.param

            cls.field_fixture = field_fixture

        if "source_fixture" not in cls.__dict__ and cls.all_sources:

            @pyt.fixture(name="source", params=cls.all_sources)
            def source_fixture(self: cls, request: pyt.FixtureRequest, field: type):
                if self.source_support[(source := request.param), field]:
                    return source
                pyt.skip(f"{field.__name__!r} does not support source {source!r}")

            cls.source_fixture = source_fixture
        super().__init_subclass__()

    @pyt.fixture(name="_setup_fixture", autouse=True)
    def __setup_fixture(self, request, model, field, source):
        self.request, self.model, self.field, self.source = (
            request,
            model,
            field,
            source,
        )

    @property
    def can_be_ordered(self) -> None:
        return isinstance(self.field, TNumTypeField | TDateTypeField | m.BooleanField)

    def check_field_setup(self, model: type[TestModel], field: type[_FT]):
        test, proxy = t.cast(
            list[type[VirtualField]],
            [model.get_field("test"), model.get_field("proxy")],
        )
        assert isinstance(test.output_field, field)
        assert isinstance(proxy.output_field, field)

    def update_db_values(self, objs: Iterable[_MT], vals: Iterable[_VT]):
        return self.update_obj_values((_db_instance_qs(o).get() for o in objs), vals)

    def update_obj_values(self, objs: Iterable[_MT], vals: Iterable[_VT]):
        for obj, expected in zip(objs, vals):
            obj.value = expected
            obj.save()

    def check_virtual_values(self, objs: Iterable[_MT], vals: Iterable[_VT], *, op=eq):
        for obj, expected in zip(objs, vals):
            for val in (obj.test, obj.proxy):
                assert op(expected, val)

    def check_real_values(self, objs: Iterable[_MT], vals: Iterable[_VT], *, op=eq):
        for obj, expected in zip(objs, vals):
            assert op(obj.value, expected)

    def check_query_results(
        self, objs: Iterable[_MT], vals: Iterable[_VT], qs: m.QuerySet[_MT] = None
    ):
        # Test query return values
        vals = tuple(vals)
        if qs is None:
            qs = self.model.objects.all()
        for sub, val in zip(objs, vals):
            oqs = qs.filter(pk=sub.pk)
            obj_by_pk = oqs.get()

            obj_only = oqs.only("pk", "test", "proxy").get()
            obj_values = oqs.values_list("pk", "test", "proxy", named=True).get()

            for obj in (obj_by_pk, obj_only, obj_values):
                assert (sub.pk, val, val) == (obj.pk, obj.test, obj.proxy)

            if vals.count(val) == 1:
                pk_by_test = qs.filter(test=val).values_list("pk", flat=True).get()
                pk_by_proxy = qs.filter(proxy=val).values_list("pk", flat=True).get()
                assert pk_by_test == pk_by_proxy == sub.pk

    def check_ordering(self, values: Iterable[_VT], qs: m.QuerySet[_MT] = None):
        if qs is None:
            qs = self.model.objects.all()

        vals = list(values)

        try:
            assert len(dict.fromkeys(vals)) == len(vals)
            vals.sort()
        except (TypeError, ValueError):
            return
        else:
            t_qs, p_qs = qs.order_by("test"), qs.order_by("proxy")
            t_res = list(t_qs.values_list("test", flat=True))
            p_res = list(p_qs.values_list("proxy", flat=True))
            assert vals == t_res == p_res

            t_qs, p_qs = qs.order_by("-test"), qs.order_by("-proxy")
            t_res = list(t_qs.values_list("test", flat=True))
            p_res = list(p_qs.values_list("proxy", flat=True))
            assert vals[::-1] == t_res == p_res

    def test_basic(
        self, factory: T_Func[_VT], model: type[TestModel], field: type[_FT]
    ):
        self.check_field_setup(model, field)

        qs: m.QuerySet[model] = model.objects.all()
        val_0, val_1 = factory(), factory()
        obj_0, obj_1 = (qs.create(value=v) for v in (val_0, val_1))
        sql = str(qs.query)

        self.check_real_values((obj_0, obj_1), (val_0, val_1))
        self.check_virtual_values((obj_0, obj_1), (val_0, val_1))

        self.check_query_results((obj_0, obj_1), (val_0, val_1))

        # swap values of the 2 objects
        self.update_obj_values((obj_0, obj_1), (val_1, val_0))

        # Test swapped values
        self.check_real_values((obj_0, obj_1), (val_1, val_0))
        self.check_virtual_values((obj_0, obj_1), (val_1, val_0))

        # Revert the values in the database.
        self.update_db_values((obj_0, obj_1), (val_0, val_1))

        # Ensure object values not yet reverted
        self.check_virtual_values((obj_0, obj_1), (val_1, val_0))

        # Refresh to get new values
        obj_0.refresh_from_db(), obj_1.refresh_from_db()

        # Test for reverted values
        self.check_virtual_values((obj_0, obj_1), (val_0, val_1))

        self.can_be_ordered and self.check_ordering((val_0, val_1))

    # @pyt.mark.skip("NOT SETUP")
    @pyt.mark.parametrize("through", ["foreignkey", "onetoonefield", "manytomanyfield"])
    def test_thourgh_related(
        self, through, factory: T_Func[_VT], model: type[_MT], source
    ):
        qs = model.objects.all()

        val_0, val_1 = factory(), factory()
        rel_0, rel_1 = (qs.create(value=v) for v in (val_0, val_1))
        if through == "manytomanyfield":
            obj_0, obj_1 = (
                r.manytomanyfield.add(o := qs.create()) or o for r in (rel_0, rel_1)
            )
        else:
            obj_0, obj_1 = (qs.create(**{through: r}) for r in (rel_0, rel_1))

        # Test the related (real) values of each object
        self.check_real_values((rel_0, rel_1), (val_0, val_1))

        self.check_virtual_values((obj_0, obj_1), (val_0, val_1))

        self.check_query_results((obj_0, obj_1), (val_0, val_1))

        # swap values of the 2 objects
        self.update_obj_values((rel_0, rel_1), (val_1, val_0))

        self.check_real_values((rel_0, rel_1), (val_1, val_0))

        obj_0.refresh_from_db(), obj_1.refresh_from_db()

        # Test the swapped values
        self.check_virtual_values((obj_0, obj_1), (val_1, val_0))

        if self.can_be_ordered:
            self.check_ordering((val_0, val_1), qs.exclude(pk__in=(rel_0.pk, rel_1.pk)))


TStrField = (
    m.CharField
    | m.TextField
    | m.EmailField
    | m.SlugField
    | m.URLField
    | m.FileField
    | m.FilePathField
)


class test_StrFields(FieldTestCase[str, TStrField, TestModel]):
    pass


TNumTypeField = (
    m.BigIntegerField
    | m.IntegerField
    | m.PositiveBigIntegerField
    | m.SmallIntegerField
    | m.PositiveSmallIntegerField
    | m.PositiveIntegerField
    | m.FloatField
    | m.DecimalField
)


class test_NumberFields(FieldTestCase[str, TNumTypeField, TestModel]):
    json_source_kwargs = {m.Field: dict(cast=True)}
    field_type_kwargs = {
        m.DecimalField: dict(decimal_places=6, max_digits=54),
    }


class test_GenericIPAddressField(
    FieldTestCase[str, m.GenericIPAddressField, TestModel]
):
    json_source_kwargs = {m.Field: dict(cast=True)}


class test_BooleanField(FieldTestCase[bool, m.BooleanField, TestModel]):
    json_source_kwargs = {m.Field: dict(cast=True)}
    pass


class test_UUIDField(FieldTestCase[UUID, m.UUIDField, TestModel]):
    # all_sources = (Src.FIELD, Src.EVAL)
    json_source_kwargs = {m.Field: dict(cast=True)}
    pass


class test_BinaryField(FieldTestCase[str, m.BinaryField, TestModel]):
    all_sources = (Src.FIELD, Src.EVAL)


TDateTypeField = m.DateField | m.DateTimeField | m.TimeField | m.DurationField


class test_DateTypesFields(FieldTestCase[str, TDateTypeField, TestModel]):
    json_source_kwargs = {m.Field: dict(cast=True)}
    source_support = DefaultDict({(Src.JSON, m.DurationField): False}, True)


class test_JSONField(FieldTestCase[dict, m.JSONField, TestModel]):
    pass


@pyt.mark.skip("NOT SETUP")
class test_ForeignKey(FieldTestCase[bool, m.ForeignKey | m.OneToOneField, TestModel]):
    @pyt.fixture
    def factory(self, model: type[_MT]):
        return lambda *a, **kw: model.objects.create(*a, **kw)

    @pyt.fixture
    def type_var(self, source: Src, field):
        return field

    @pyt.fixture
    def kwargs(self, kwargs, type_var):
        if type_var:
            kwargs = {**kwargs, "to": "self"}
        return kwargs

    @pyt.fixture
    def def_kwargs(self, def_kwargs, field, kwargs):
        return {**def_kwargs, "proxy": VirtualField[field]("test", **kwargs)}
