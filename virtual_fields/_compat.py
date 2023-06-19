from abc import ABC, abstractmethod
from collections import abc
from functools import cached_property, partial, wraps
from typing import TYPE_CHECKING, ClassVar, TypeVar
from weakref import WeakSet

from django.apps import apps
from django.db import models as m
from django.db.models.options import Options
from django.db.models.query import QuerySet
from django.dispatch import receiver
from typing_extensions import Self

if TYPE_CHECKING:
    from .fields import VirtualField
    from .models import VirtualizedModel, VirtualizedOptions


_T_Model = TypeVar("_T_Model", bound="VirtualizedModel", covariant=True)
_T_Field = TypeVar("_T_Field", bound=m.Field, covariant=True)


def _on_class_prepared(sender: type["VirtualizedModel"], *, disconnect=None, **kwds):
    from .models import ImplementsVirtualFields

    ImplementsVirtualFields.setup(sender)
    if disconnect is False:
        return
    m.signals.class_prepared.disconnect(_on_class_prepared, sender)


def add_virtual_field_support(cls: type["VirtualizedModel"]):
    try:
        opts = cls._meta
        apps.get_registered_model(opts.app_label, opts.model_name)
    except LookupError:
        m.signals.class_prepared.connect(_on_class_prepared, cls, weak=False)
    else:
        _on_class_prepared(cls, disconnect=False)


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

    @patch()
    def _iter_virtual_fields(
        self: "VirtualizedOptions", filter, /, *matches, fields=None
    ):
        if isinstance(filter, str):
            attr = filter
            filter = lambda field: getattr(field, attr)
        fields = self.virtual_fields.values() if fields is None else fields
        if matches:
            for field in fields:
                if filter(field) in matches:
                    yield field
        else:
            for field in fields:
                if filter(field):
                    yield field

    @patch(wrap=cached_property)
    def virtual_fields(self: "VirtualizedOptions"):
        from .fields import VirtualField

        fields = {
            field.name: field
            for field in self.get_fields()
            if isinstance(field, VirtualField)
        }
        return fields

    @patch(wrap=cached_property)
    def cached_virtual_fields(self: "VirtualizedOptions"):
        return {k: v for k, v in self.virtual_fields.items() if v.cache}

    @patch(wrap=cached_property)
    def deferred_virtual_fields(self: "VirtualizedOptions"):
        return {k: v for k, v in self.virtual_fields.items() if v.defer}

    @patch(wrap=cached_property)
    def concrete_virtual_fields(self: "VirtualizedOptions"):
        return {k for k, v in self.virtual_fields.items() if v.concrete}

    @patch(wrap=cached_property)
    def virtual_fields_to_delete_on_refresh(self: "VirtualizedOptions"):
        from virtual_fields.fields import Behaviour

        fields = self._iter_virtual_fields("on_model_refresh", Behaviour.DELETE)
        return {field.name: field for field in fields}

    @patch(wrap=cached_property)
    def virtual_fields_to_reload_on_refresh(self: "VirtualizedOptions"):
        from virtual_fields.fields import Behaviour

        fields = self._iter_virtual_fields("on_model_refresh", Behaviour.RELOAD)
        return {field.name: field for field in fields}

    @patch(wrap=cached_property)
    def virtual_fields_to_delete_on_save(self: "VirtualizedOptions"):
        from virtual_fields.fields import Behaviour

        fields = self._iter_virtual_fields("on_model_save", Behaviour.DELETE)
        return {field.name: field for field in fields}

    @patch(wrap=cached_property)
    def virtual_fields_to_reload_on_save(self: "VirtualizedOptions"):
        from virtual_fields.fields import Behaviour

        fields = self._iter_virtual_fields("on_model_save", Behaviour.RELOAD)
        return {field.name: field for field in fields}

    @patch(wrap=cached_property)
    def virtual_fields_to_delete_on_add(self: "VirtualizedOptions"):
        from virtual_fields.fields import Behaviour

        fields = self._iter_virtual_fields("on_model_add", Behaviour.DELETE)
        return {field.name: field for field in fields}

    @patch(wrap=cached_property)
    def virtual_fields_to_reload_on_add(self: "VirtualizedOptions"):
        from virtual_fields.fields import Behaviour

        fields = self._iter_virtual_fields("on_model_add", Behaviour.RELOAD)
        return {field.name: field for field in fields}

    Options.REVERSE_PROPERTIES |= {
        "virtual_fields",
        "cached_virtual_fields",
        "deferred_virtual_fields",
        "concrete_virtual_fields",
        "virtual_fields_to_delete_on_refresh",
        "virtual_fields_to_reload_on_refresh",
        "virtual_fields_to_delete_on_save",
        "virtual_fields_to_reload_on_save",
        "virtual_fields_to_delete_on_add",
        "virtual_fields_to_reload_on_add",
    }


def _install():
    _patch_model_options()
    if not hasattr(QuerySet, "select_virtual"):

        def select_virtual(self: QuerySet[_T_Model], *fields) -> QuerySet[_T_Model]:
            opts, qs = self.model._meta, self._chain()
            allowed = opts.virtual_fields
            for name in fields:
                qs = allowed[name].add_to_query(qs)
            return qs

        QuerySet.select_virtual = select_virtual
