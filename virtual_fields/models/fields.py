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

from django.core.exceptions import FieldError, ImproperlyConfigured
from django.db import models as m
from django.db.models import Q
from django.db.models.constants import LOOKUP_SEP
from django.db.models.expressions import BaseExpression, Combinable
from django.db.models.functions import Cast, Coalesce
from django.db.models.query_utils import DeferredAttribute
from django.dispatch import receiver
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
_T_PathInfo = tuple[list, _T_Field, tuple, list[str]]

logger = getLogger(__name__)

_virtual_field_models = set()


def _add_virtual_field_support(model: type[_T_Model]):
    if not (model in _virtual_field_models or model._meta.abstract):
        _virtual_field_models.add(model)
        m.signals.post_save.connect(_post_save_receiver, model, weak=False)

    return model


@receiver(m.signals.class_prepared, weak=False)
def __on_class_prepared(sender: type[_T_Model], **kwds):
    if sender not in _virtual_field_models:
        if {*sender.__mro__[1:-1]} & _virtual_field_models:
            _add_virtual_field_support(sender)


def _post_save_receiver(sender, instance: _T_Model, **kwargs):
    dct = instance.__dict__
    for n, f in instance.__class__._meta.cached_virtual_fields.items():
        if (at := f.attname) in dct:
            delattr(instance, at)


def _flatten(obj, types=tuple | list):
    if isinstance(obj, types):
        yield from obj
    else:
        yield obj


class VirtualWrapper(m.ExpressionWrapper, Generic[_T_Field]):
    def __init__(
        self,
        expression: Q | Combinable | str,
        output_field: _T_Field = None,
    ) -> None:
        super().__init__(expression, output_field)


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
    concrete: bool | None
    model: _T_Model
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
    _output_type_: Final[type[_T_Field]] = None
    _output_args_: ClassVar = None
    _output_kwargs_: ClassVar = None
    _init_defaults_ = {
        # "null": True,
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
        "error_mess testages",
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

    def __new__(cls: type[Self], *a, output_field: _T_Field = None, **kw):
        if output_field is not None:
            typ, bound = output_field.__class__, cls._output_type_
            if bound is None:
                cls = cls[typ]
            elif not issubclass(typ, bound):
                raise ImproperlyConfigured(
                    f"Invalid argument `output_field`. "
                    f"Expected {bound.__name__!r} not {typ.__name__!r}."
                )
        self = object.__new__(cls)
        return self

    @overload
    def __init__(
        self,
        *expressions: _T_Fn | Combinable | m.Q | str,
        output_field: _T_Field = None,
        defer: bool | None = None,
        cache: bool | None = None,
        verbose_name: str = None,
        name: str = None,
        max_length: int = None,
        unique: bool = False,
        blank: bool = False,
        null: bool = False,
        cast: bool = False,
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
        *expressions: _T_Fn | Combinable | m.Q | str,
        output_field=None,
        defer: bool = None,
        cache: bool | None = None,
        cast: bool = None,
        fget: _T_Fn = None,
        fset: _T_Fn = None,
        fdel: _T_Fn = None,
        **kwargs,
    ):
        self.expressions = expressions
        self.defer, self.cast = defer, cast
        kwargs, bfk = self._init_defaults_ | kwargs, self._base_field_kwargs_
        super().__init__(**{k: v for k, v in kwargs.items() if k in bfk})
        self.fget, self.fset, self.fdel, self.cache = fget, fset, fdel, cache

        if output_field is None and self._output_type_:
            kwargs = (self._output_kwargs_ or {}) | kwargs
            output_field = self._output_type_(**kwargs)
        self._output_field = output_field

    @cached_property
    def output_field(self) -> _T_Field:
        out, src = self._output_field, self.source_output_field  # , self.source_fields
        return src if out is None else out

    @cached_property
    def source_output_field(self) -> _T_Field | None:
        src, qs = self.source_expression, self._queryset
        try:
            return Coalesce(src, None).resolve_expression(qs.query).output_field
        except FieldError:
            pass

    @cached_property
    def source_fields(self) -> tuple[_T_Field, ...]:
        src = Coalesce(self.source_expression, None)
        fields = tuple(f for f in src.get_source_fields() if f is not None)
        return fields

    @property
    def empty_strings_allowed(self):
        if out := self._output_field:
            return out.empty_strings_allowed
        return False

    @cached_property
    def final_expression(self):
        expr, out, cast = self.source_expression, self.output_field, self.cast
        if cast:
            expr = Cast(expr, out)
        if self.has_default():
            expr = Coalesce(expr, m.Value(self.get_default()), output_field=out)
        elif not cast:
            expr = m.ExpressionWrapper(expr, out)
        expr.target = self
        return expr

    @cached_property
    def source_expression(self):
        src, out = self.source_expressions, self._output_field
        return src[0] if len(src) == 1 else Coalesce(*src, output_field=out)

    @cached_property
    def source_refs(self):
        src, name = self.source_expressions, self.name
        refs = tuple(
            f
            for e in src
            for f in (e.flatten() if hasattr(e, "flatten") else [e])
            if isinstance(f, m.F)
        )
        return refs

    @cached_property
    def source_fields(self):
        name, src, opts = self.name, self.source_refs, self.model._meta

        q = opts.virtual_fields_queryset.query
        for it in src if len(src) == 1 else ():
            path_info: _T_PathInfo = q.names_to_path(it.name.split(LOOKUP_SEP), opts)
            path, final_field, targets, names = path_info
            if final_field:
                final_name, final_model = final_field.name, final_field.model
            pass
        return src

    @cached_property
    def source_expressions(self) -> tuple[Combinable | BaseExpression, ...]:
        cls, expressions = self.model, self.expressions
        src = tuple(
            v
            if hasattr(v, "resolve_expression")
            else m.F(v)
            if isinstance(v, str)
            else m.Value(v)
            for e in expressions
            for v in _flatten(e(cls) if callable(e) else e)
            if v is not None
        )
        return src

    @cached_property
    def _queryset(self):
        return m.QuerySet[_T_Model](model=self.model)

    @cached_property
    def cached_col(self):
        expr, qs = self.final_expression, self._queryset
        annotation = expr.resolve_expression(qs.query, allow_joins=True, reuse=None)
        return annotation

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
            else True
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

    def get_internal_type(self):
        return "VirtualField"

    def db_type(self, connection):
        # TODO: Remove this. Not getting called
        return None

    def get_filter_kwargs_for_object(self, obj):
        """TODO: Remove if breakpoint not HIT
        Return a dict that when passed as kwargs to self.model.filter(), would
        yield all instances having the same value for this field as obj has.
        """
        rv = {self.name: getattr(obj, self.attname)}
        return rv

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
        _add_virtual_field_support(cls)
        setattr(cls, self.attname, self.descriptor_class(self))

    def get_attname_column(self):
        """Sets column to `None` for deferred fields to prevent selection."""
        attname, column = super().get_attname_column()
        return attname, None if self.is_deferred else column
