import typing as t

import pytest as pyt
from django.db import models as m
from django.db.models.fields.json import KT, JSONField

from tests.test_virtual_fields.models import ExprSource as Src

if t.TYPE_CHECKING:
    from tests.test_virtual_fields.models import T_Func, TestModel
    from virtual_fields import VirtualField


@pyt.fixture
def base_model():
    from tests.test_virtual_fields.models import TestModel

    return TestModel


@pyt.fixture
def to_python(field, base_model: "type[TestModel]"):
    return base_model.get_field(field, m.Field()).to_python


@pyt.fixture
def factory(factories, field):
    return factories[field]


@pyt.fixture
def field_name(field: type, base_model: "type[TestModel]"):
    return base_model.get_field_name(field)


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
    from virtual_fields import VirtualField

    return VirtualField[type_var] if type_var is not None else VirtualField


@pyt.fixture
def def_kwargs(src_field_alias, through: str, source: Src):
    from virtual_fields import VirtualField

    if src_field_alias:
        kwds = {src_field_alias: VirtualField(f"{through}__json", defer=True)}
        return kwds
    return {}


@pyt.fixture
def define(source: Src, field, new, def_kwargs, base_model: "type[TestModel]"):
    def_kwargs = {"source": source, "field_type": field, **def_kwargs}

    def func(*bases, test=def_kwargs.pop("test", None), **kw):
        test = new() if test is None else test
        return base_model.define(*bases, test=test, **def_kwargs | kw)

    return func


@pyt.fixture
def new(cls: type["VirtualField"], expression, kwargs: dict):
    def func(expression=expression, **kw):
        return cls(expression, **kwargs | kw)

    return func


@pyt.fixture
def model(define: "T_Func[type[m.Model]]"):
    return define()


@pyt.fixture
def kwargs(request: pyt.FixtureRequest, field: type[m.Field], source):
    return {}
