from abc import ABC, abstractmethod
from collections import abc
from functools import cached_property, partial
from typing import TYPE_CHECKING, ClassVar, TypeVar

from django.core.exceptions import FieldDoesNotExist
from django.db import models as m
from django.db.models.options import Options
from django.db.models.query import QuerySet
from typing_extensions import Self

if TYPE_CHECKING:
    from .fields import VirtualField

    class Model(m.Model):
        _meta: ClassVar["ModelOptions[Self]"]

else:
    Model = m.Model


_T_Model = TypeVar("_T_Model", bound=Model, covariant=True)
_T_Field = TypeVar("_T_Field", bound=m.Field, covariant=True)


class ModelOptions(Options, ABC):
    @property
    @abstractmethod
    def virtual_fields(self) -> abc.Mapping[str, "VirtualField"]:
        ...

    @property
    @abstractmethod
    def cached_virtual_fields(self) -> abc.Mapping[str, "VirtualField"]:
        ...

    @property
    @abstractmethod
    def deferred_virtual_fields(self) -> abc.Mapping[str, "VirtualField"]:
        ...

    @property
    @abstractmethod
    def virtual_fields_queryset(self) -> m.QuerySet[_T_Model]:
        ...

    @abstractmethod
    def get_virtual_field(self, name: str):
        ...


# class _FieldMap(dict[str, _T_Field]):
#     __slots__ = ("fallbacks",)

#     def __init__(self, val=(), *fallbacks, **kwargs):
#         super().__init__(val, **kwargs)
#         self.fallbacks = fallbacks

#     def __missing__(self, key):
#         for fb in self.fallbacks:
#             try:
#                 return fb[key]
#             except KeyError:
#                 pass
#         raise KeyError(key)


def _patcher(*a, **kw):
    def patch(name: str = None, value=None, *, wrap=None, override=False, cls=Options):
        def deco(val):
            at = val.__name__ if name is None else name
            if override or not hasattr(cls, at):
                val = val if wrap is None else wrap(val)
                setattr(cls, at, val)
                if callable(fn := getattr(val, "__set_name__", None)):
                    fn(cls, at)
            return value

        return deco if value is None else deco(value)

    if TYPE_CHECKING:
        return patch
    return partial(patch, *a, **kw)


def _patch_model_options():
    patch = _patcher(cls=Options)

    # @patch
    # def get_virtual_field(self: ModelOptions, name: str):
    #     try:
    #         return self.virtual_fields[name]
    #     except KeyError:
    #         raise FieldDoesNotExist(f"{name}")

    @patch(wrap=cached_property)
    def virtual_fields(self: ModelOptions):
        from .fields import VirtualField

        # qs = self.virtual_fields_queryset
        by_attname = {}
        fields = {}  # _FieldMap((), by_attname)
        for field in self.get_fields():
            if isinstance(field, VirtualField):
                name, attname = field.name, getattr(field, "attname", None)
                # if attname and name != attname:
                #     by_attname[attname] = field
                fields[name] = field
                # qs.query.add_annotation(field.final_expression, name, field.concrete)
        return fields

    @patch(wrap=cached_property)
    def cached_virtual_fields(self: ModelOptions):
        return {k: v for k, v in self.virtual_fields.items() if v.cache}

    Options.REVERSE_PROPERTIES |= {
        "virtual_fields",
        "cached_virtual_fields",
        "deferred_virtual_fields",
    }


_patch_model_options()


if not hasattr(QuerySet, "select_virtual"):

    def select_virtual(self: QuerySet[_T_Model], *fields) -> QuerySet[_T_Model]:
        opts, qs = self.model._meta, self._chain()
        allowed = opts.virtual_fields
        for name in fields:
            qs = allowed[name].add_to_query(qs)
        return qs

    QuerySet.select_virtual = select_virtual
