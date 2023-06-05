from abc import ABC, abstractmethod
from collections import abc
from functools import cached_property
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


class ModelOptions(Options, ABC):
    @property
    @abstractmethod
    def virtual_fields_map(self) -> abc.Mapping[str, "VirtualField"]:
        ...

    @abstractmethod
    def get_virtual_field(self, name: str):
        ...


if not hasattr(Options, "virtual_fields_map"):

    def get_virtual_field(self: ModelOptions, name: str):
        try:
            return self.virtual_fields_map[name]
        except KeyError:
            raise FieldDoesNotExist(f"{name}")

    def virtual_fields_map(self: ModelOptions):
        from .fields import VirtualField

        return {f.attname: f for f in self.get_fields() if isinstance(f, VirtualField)}

    Options.FORWARD_PROPERTIES.add("virtual_fields_map")
    Options.virtual_fields_map = cached_property(virtual_fields_map)
    Options.virtual_fields_map.__set_name__(Options, "virtual_fields_map")
    Options.get_virtual_field = get_virtual_field


if not hasattr(QuerySet, "select_virtual"):

    def select_virtual(self: QuerySet[_T_Model], *fields) -> QuerySet[_T_Model]:
        opts, qs = self.model._meta, self._chain()
        allowed, query = opts.virtual_fields_map, qs.query
        for name in fields:
            if name not in allowed:
                opts.get_field(name)
                raise ValueError(f"field {name!r} is not a VirtualField.")
            query.add_annotation(m.F(name), name)
        return qs

    QuerySet.select_virtual = select_virtual
    QuerySet.filter
