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
    NamedTuple,
    TypeVar,
    get_origin,
    overload,
)

from django.core.exceptions import FieldError, ImproperlyConfigured
from django.db import models as m
from django.db.models import base as models_mod
from django.db.models.constants import LOOKUP_SEP
from django.db.models.expressions import (
    BaseExpression,
    Combinable,
    Expression,
    ExpressionWrapper,
    F,
    Value,
)
from django.db.models.functions import Cast, Coalesce
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
_T_Expr = TypeVar("_T_Expr", Combinable, m.Q)
_T_Fn = abc.Callable[..., Any]

logger = getLogger(__name__)

_virtual_field_models = set()

DEFERRED = models_mod.DEFERRED


def _add_virtual_field_support(model: type[_T_Model]):
    if not (model in _virtual_field_models or model._meta.abstract):
        _virtual_field_models.add(model)
        m.signals.post_save.connect(_post_save_receiver, model, weak=False)

    return model


@receiver(m.signals.class_prepared, weak=False)
def __on_class_prepared(sender: type[_T_Model], **kwds):
    if sender not in _virtual_field_models:
        bases = {*sender.__mro__[1:-1]}
        (bases & _virtual_field_models) and _add_virtual_field_support(sender)


def _post_save_receiver(sender, instance: _T_Model, **kwargs):
    dct = instance.__dict__
    for n, f in instance.__class__._meta.cached_virtual_fields.items():
        if (at := f.attname) in dct:
            delattr(instance, at)


def _attrsetter_decorator(name: str, typ: type = Any, *, call=False):
    def decorator(self, val: typ = None):
        def setter(v):
            getattr(self, name)(v) if call else setattr(self, name, v)

        return setter if val is None else setter(val)

    return decorator


def _db_instance_qs(obj: _T_Model, using=None, *, filter=True):
    man = obj.__class__._meta.base_manager
    qs: m.Manager[_T_Model] = man.db_manager(using, hints={"instance": obj})
    return qs.all() if filter is False else qs.filter(pk=obj.pk)


def coalesced(expr: _T_Expr, /, *exprs: _T_Expr):
    return (
        Coalesce(expr, *exprs)
        if exprs
        else expr
        if isinstance(expr, Expression)
        else ExpressionWrapper(expr, None)
    )


class FieldPathInfo(NamedTuple):
    path: list
    field: _T_Field
    targets: tuple = ()
    name: tuple[str] = ()
    src: "VirtualField" = None


class VirtualFieldDescriptor:
    field: "VirtualField"
    cache: bool = None
    func: _T_Fn = None
    attname: str
    fieldname: str

    def __init__(self, field: "VirtualField"):
        self.field = field
        self.attname, self.fieldname = field.attname, field.name
        self.cache = field.cache if self.cache is None else self.cache

        if (func := self.__class__.func) is not None:
            self.get_instance_value = func

        if self.get_default is None:
            self.get_default = field._get_default

    def __get__(self, obj: _T_Model, cls=None):
        if obj is None:
            return self

        cache = self.cache
        if cache and (name := self.attname) in (data := self.get_cache_dict(obj)):
            return data[name]

        val = self.get_instance_value(obj)
        if val is NotImplemented:
            val = self.get_db_value(obj)
            if val is None:
                val = self.get_default()
                if val is DEFERRED:
                    return
        elif val is DEFERRED:
            return

        if cache:
            data[name] = val
        return val

    def get_cache_dict(self, obj: _T_Model):
        return obj.__dict__

    def get_db_value(self, obj: _T_Model):
        qs = self.field.get_queryset_for_object(obj)
        return qs.values_list(self.fieldname, flat=True).get()

    def get_instance_value(self, obj: _T_Model):
        return self.get_default() if obj._state.adding else self.get_db_value(obj)

    @overload
    def get_default(self):
        ...

    get_default = None


class VirtualField(m.Field, Generic[_T_Field]):
    description = _("A virtual field. Uses query annotations to return computed value.")
    expressions: m.expressions.Combinable | m.Q | str
    empty_strings_allowed = False
    defer: bool = False
    cache: bool | None
    concrete: bool | None
    model: _T_Model
    base_descriptor_class = VirtualFieldDescriptor
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
                cls = get_origin(cls) or cls
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
        kwargs, bfk = self._init_defaults_ | kwargs, self._base_field_kwargs_
        super().__init__(**{k: v for k, v in kwargs.items() if k in bfk})
        self.set_source_expressions(*expressions)
        self.fget, self.fset, self.fdel, self.cast = fget, fset, fdel, cast

        if defer is not None:
            self.defer = defer
        if cache is not None:
            self.cache = cache

        if output_field is None and self._output_type_:
            kwargs = (self._output_kwargs_ or {}) | kwargs
            output_field = self._output_type_(**kwargs)
        self._output_field = output_field

    getter = _attrsetter_decorator("fget", _T_Fn)
    setter = _attrsetter_decorator("fset", _T_Fn)
    deleter = _attrsetter_decorator("fdel", _T_Fn)
    expression = _attrsetter_decorator("set_source_expressions", _T_Fn, call=True)

    @cached_property
    def cache(self):
        return (None, None, None) == (self.fget, self.fset, self.fdel)

    @cached_property
    def defer(self):
        return self.fget is not None

    @cached_property
    def output_field(self) -> _T_Field:
        return self._output_field or self.source_output_field

    @cached_property
    def final_expression(self):
        src, out, cast = self.raw_expression, self.output_field, self.cast
        expr = (Cast if cast else ExpressionWrapper)(src, output_field=out)
        expr.target = self
        return expr

    @cached_property
    def source_output_field(self) -> _T_Field | None:
        q, src = self._queryset.query, self.raw_expression
        try:
            return src.resolve_expression(q).output_field
        except FieldError:
            pass

    @cached_property
    def raw_expression(self):
        return coalesced(*self.source_expressions)

    @cached_property
    def source_expressions(self):
        return tuple(self._iter_source_expressions())

    @cached_property
    def _queryset(self):
        return m.QuerySet[_T_Model](model=self.model)

    @cached_property
    def cached_col(self):
        expr, qs = self.final_expression, self._queryset
        annotation = expr.resolve_expression(qs.query)
        return annotation

    @cached_property
    def descriptor_class(self):
        fget, fset, fdel = self.get_fget(), self.get_fset(), self.get_fdel()
        return self._define_descriptor_class(fget, fset, fdel, cached=self.cache)

    def get_col(self, alias, output_field=None):
        return self.cached_col

    def get_internal_type(self):  # pragma: no cover
        return "VirtualField"

    def clean(self, value, model_instance):
        return self.output_field.clean(value, model_instance)

    def formfield(self, **kwargs):
        return self.output_field.formfield(**kwargs)

    def contribute_to_class(self, cls, name, private_only=None):
        super().contribute_to_class(cls, name, private_only is not False)
        _add_virtual_field_support(cls)
        assert isinstance(getattr(cls, self.attname), self.descriptor_class)

    def set_attributes_from_name(self, name):
        super().set_attributes_from_name(name)
        self.concrete = not self.defer

    def set_source_expressions(self, *expressions):
        self.expressions = expressions

    def add_to_query(self, qs: m.QuerySet[_T_Model], alias=None, select=True):
        name = self.name
        qs.query.add_annotation(F(name), alias or name, select)
        return qs

    def get_queryset_for_object(self, obj: _T_Model):
        return self.add_to_query(_db_instance_qs(obj))

    def get_fget(self):
        fget = self.fget
        return fget

    def get_fset(self):
        return self.fset

    def get_fdel(self):
        return self.fdel

    def _define_descriptor_class(
        field,
        /,
        fget=None,
        fset=None,
        fdel=None,
        *,
        cached: bool,
        base: type[VirtualFieldDescriptor] = None,
        **kwds,
    ):
        if base is None:
            base = field.base_descriptor_class

        class FieldDescriptor(base):
            cache = cached
            func = fget

            if fset is not None:

                def __set__(self, obj, val):
                    return fset(obj, val)

            if fdel is not None:

                def __delete__(self, obj):
                    return fdel(obj)

            vars().update(kwds)

        return FieldDescriptor

    def _iter_source_expressions(self):
        cls, expressions = self.model, self.expressions
        v: Combinable | BaseExpression
        for e in expressions:
            if callable(e):
                e = e(cls)
            for v in e if isinstance(e, (tuple, list, abc.Iterator)) else (e,):
                if v is None:
                    pass
                elif hasattr(v, "resolve_expression"):
                    yield v
                elif isinstance(v, str):
                    yield F(v)
                else:
                    yield Value(v)

    def __get_flat_source_expressions(self):  # pragma: no cover
        raw = self.raw_expression
        return (f if isinstance(f, F) else None for f in raw.flatten())

    def __get_source_fields(
        self, *, recursive=None, src: "VirtualField" = None
    ):  # pragma: no cover
        f: _T_Field | VirtualField
        opts, qs, deep = self.model._meta, self._queryset, recursive is not False
        to_path = qs.query.names_to_path.__get__(qs.query)

        for expr in filter(None, self.__get_flat_source_expressions()):
            if expr is None:
                yield None
            else:
                path = to_path(expr.name.split(LOOKUP_SEP), opts)
                info = FieldPathInfo(*path, src=src)
                if deep is True is hasattr(f := info.field, "get_source_fields"):
                    yield from f.__get_source_fields(recursive=recursive, src=self)
                else:
                    yield info
