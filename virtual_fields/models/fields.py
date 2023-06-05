from collections import abc
from functools import reduce
from logging import getLogger
from operator import methodcaller, or_
from threading import RLock
from types import new_class
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Final,
    Generic,
    TypeVar,
    get_origin,
    overload,
)

from django.db import models as m
from django.db.models.query_utils import DeferredAttribute
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from typing_extensions import Self

if TYPE_CHECKING:
    from ._compat import Model

__all__ = [
    "VirtualField",
]

_T_Field = TypeVar("_T_Field", bound=m.Field, covariant=True)
_T_Model = TypeVar("_T_Model", bound="Model", covariant=True)
_T_Fn = abc.Callable[..., Any]
logger = getLogger(__name__)


class VirtualFieldDescriptor(DeferredAttribute):
    field: "VirtualField"

    # def __get__(self, obj: _T_Model, typ=None):
    #     return

    # def __set__(self, obj: _T_Model, val):
    #     return

    def _check_parent_chain(self, obj: _T_Model):
        if (val := super()._check_parent_chain(obj)) is None and not obj._state.adding:
            qs: m.QuerySet = obj.__class__._default_manager
            val = qs.values_list(self.field.attname, flat=True).get(pk=obj.pk)
        return val


class VirtualField(m.Field, Generic[_T_Field]):
    description = _("A virtual field. Uses query annotations to return computed value.")
    expressions: m.expressions.Combinable | m.Q | str
    defer: bool = False
    cache: bool | None
    model: m.Model
    descriptor_class = VirtualFieldDescriptor
    fget: _T_Fn | None
    fset: _T_Fn | None
    fdel: _T_Fn | None
    is_virtual: bool = True
    __output_typed_: Final = {}
    __out_lock: Final = RLock()

    _output_types_default_kwargs_ = {
        m.CharField: {
            "max_length": 255,
        },
        m.ForeignKey: {
            "on_delete": lambda: m.DO_NOTHING,
        },
    }
    _output_type_: Final = None
    _output_args_: ClassVar = None
    _output_kwargs_: ClassVar = None
    _init_defaults_ = {
        "editable": False,
        "serialize": False,
    }
    _base_field_kwargs_ = (
        "verbose_name",
        "name",
        "primary_key",
        "max_length",
        "unique",
        "blank",
        "null",
        "db_index",
        "rel",
        "default",
        "editable",
        "serialize",
        "unique_for_date",
        "unique_for_month",
        "unique_for_year",
        "choices",
        "help_text",
        "db_column",
        "db_tablespace",
        "auto_created",
        "validators",
        "error_messages",
        "db_comment",
    )

    def __class_getitem__(cls, params):
        out: type[_T_Field] = params[0] if isinstance(params, (tuple, list)) else params
        out, base, final = get_origin(out) or out, cls._output_type_, cls

        if base is None and isinstance(out, type) and issubclass(out, m.Field):
            assert base is None or issubclass(
                out, base
            ), f"must be a subtype of {base.__name__}"
            cache = cls.__output_typed_
            if (final := cache.get(out)) is None:
                with cls.__out_lock:
                    if (final := cache.get(out)) is None:
                        name = f"{out.__name__.replace('Field', '')}{cls.__name__}"
                        module, qualname = cls.__module__, f"{cls.__qualname__}.{name}"
                        by_typ = cls._output_types_default_kwargs_
                        kwds = reduce(
                            or_,
                            filter(None, map(by_typ.get, out.__mro__[::-1])),
                            cls._output_kwargs_ or {},
                        )
                        cache[out] = final = new_class(
                            name,
                            (cls[_T_Field],),
                            None,
                            methodcaller(
                                "update",
                                {
                                    "__module__": module,
                                    "__qualname__": qualname,
                                    "_output_type_": out,
                                    "_output_field_kwargs_": kwds,
                                },
                            ),
                        )
        return super(cls, final).__class_getitem__(params)

    if not TYPE_CHECKING:

        def __new__(cls: type[Self], *a, output_field=None, **kw):
            if output_field is not None is cls._output_type_:
                cls = cls[output_field.__class__]
            self = object.__new__(cls)
            return self

    @overload
    def __init__(
        self,
        *expressions: _T_Fn | m.expressions.Combinable | m.Q | str,
        output_field: _T_Field = None,
        defer: bool | None = None,
        cache: bool | None = None,
        verbose_name: str = None,
        name: str = None,
        max_length: int = None,
        unique: bool = False,
        blank: bool = False,
        null: bool = False,
        db_cast: bool = False,
        db_index: bool = False,
        default=...,
        editable: bool = False,
        serialize: bool = False,
        unique_for_date=None,
        unique_for_month=None,
        unique_for_year=None,
        choices=None,
        help_text="",
        validators=(),
        error_messages=None,
        fget: _T_Fn = None,
        fset: _T_Fn = None,
        fdel: _T_Fn = None,
    ):
        ...

    def __init__(
        self,
        *expressions: m.expressions.Combinable | m.Q | str,
        output_field=None,
        defer: bool = None,
        cache: bool | None = None,
        db_cast: bool = None,
        fget: _T_Fn = None,
        fset: _T_Fn = None,
        fdel: _T_Fn = None,
        **kwargs,
    ):
        self.expressions = expressions
        self.defer, self.db_cast = defer, db_cast
        kwargs, bfk = self._init_defaults_ | kwargs, self._base_field_kwargs_
        super().__init__(**{k: v for k, v in kwargs.items() if k in bfk})
        self.fget, self.fset, self.fdel, self.cache = fget, fset, fdel, cache
        if output_field is None and self._output_type_:
            kwargs = (self._output_kwargs_ or {}) | kwargs
            output_field = self._output_type_(**kwargs)
        self.output_candidate = output_field

    @cached_property
    def output_field(self) -> _T_Field:
        return self.final_expression.output_field

    @cached_property
    def empty_strings_allowed(self):
        return o.empty_strings_allowed if (o := self.output_field) else False

    @cached_property
    def final_expression(self):
        (expr, *extra), out = self._get_expressions(), self.output_candidate
        self.has_default() and extra.append(m.Value(self.get_default()))

        if extra:
            expr = m.functions.Coalesce(expr, *extra, output_field=out)
        elif isinstance(expr, str):
            expr = m.F(f"{expr}")

        if self.db_cast:
            assert out is not None, f""
            expr = m.functions.Cast(expr, out)
        else:
            expr = m.ExpressionWrapper(expr, out)
        expr.target = self
        return expr

    @cached_property
    def cached_col(self):
        model = self.model
        name, qs = self.name, m.QuerySet(model=model).select_related()
        qs._fields = {f.name for f in model._meta.get_fields() if f.name != name}
        qs = qs.annotate(**{name: self.final_expression})
        rv = qs.query.annotations[name]
        return rv

    def get_col(self, alias, output_field=None):
        return self.cached_col

    @property
    def is_deferred(self) -> bool:
        return self.fget is not None if (rv := self.defer) is None else rv

    @property
    def is_cached(self) -> bool:
        return (
            rv
            if (rv := self.cache) is not None
            else self.fget is None
            if self.is_deferred
            else False
        )

    def getter(self, func: _T_Fn = None):
        def decorator(fn):
            self.fget = fn

        return decorator if func is None else decorator(func)

    def setter(self, func: _T_Fn = None):
        def decorator(fn):
            self.fset = fn

        return decorator if func is None else decorator(func)

    def deleter(self, func: _T_Fn = None):
        def decorator(fn):
            self.fdel = fn

        return decorator if func is None else decorator(func)

    def expression(self, func: _T_Fn = None):
        def decorator(fn):
            self.expressions = (fn,)

        return decorator if func is None else decorator(func)

    def _get_expressions(self):
        return (e(self.model) if callable(e) else e for e in self.expressions)

    def get_internal_type(self):
        return "VirtualField"

    def db_type(self, connection):
        # TODO: Remove this. Not getting called
        return None

    def select_format(self, compiler, sql, params):
        """
        TODO: Remove this and implement an Expression.
              Check `resolve_expression` and `as_sql` on `BaseExpression`
            EDIT: GETS CALLED TO RESOLVE RELATED

        Custom format for select clauses. For example, GIS columns need to be
        selected as AsText(table.col) on MySQL as the table.col data can't be
        used by Django.
        """
        _sql, _params = super().select_format(compiler, sql, params)
        return _sql, _params

    def clean(self, value, model_instance):
        return self.output_field.clean(value, model_instance)

    def formfield(self, **kwargs):
        return self.output_field.formfield(**kwargs)

    def contribute_to_class(self, cls, name, private_only=None):
        super().contribute_to_class(cls, name, private_only is not False)
        setattr(cls, self.attname, self.descriptor_class(self))

    def get_attname_column(self):
        """Sets column to `None` for deferred fields to prevent selection."""
        attname, column = super().get_attname_column()
        return attname, None if self.is_deferred else column
