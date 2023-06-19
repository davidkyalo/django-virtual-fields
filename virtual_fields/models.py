from abc import ABC, abstractmethod
from collections import abc
from functools import wraps
from typing import TYPE_CHECKING, ClassVar, Final, TypeVar

from django.db import models as m
from django.db.models.options import Options
from typing_extensions import Self

from ._util import _db_instance_qs

if TYPE_CHECKING:
    from .fields import VirtualField


_T_Model = TypeVar("_T_Model", bound="VirtualizedModel", covariant=True)
_T_Field = TypeVar("_T_Field", bound=m.Field, covariant=True)


def _mro_get(cls: type, attr, default=None):
    for b in cls.__mro__:
        if attr in b.__dict__:
            return b.__dict__[attr]
    return default


class VirtualizedOptions(Options, ABC):
    @abstractmethod
    def _iter_virtual_fields(
        self,
        filter: str | abc.Callable,
        /,
        *matches,
        items: abc.Iterable["VirtualField"] = None,
    ) -> abc.Iterator["VirtualField"]:
        ...

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
    def concrete_virtual_fields(self) -> abc.Mapping[str, "VirtualField"]:
        ...

    @property
    @abstractmethod
    def virtual_fields_to_delete_on_add(self) -> abc.Mapping[str, "VirtualField"]:
        ...

    @property
    @abstractmethod
    def virtual_fields_to_reload_on_add(self) -> abc.Mapping[str, "VirtualField"]:
        ...

    @property
    @abstractmethod
    def virtual_fields_to_delete_on_refresh(self) -> abc.Mapping[str, "VirtualField"]:
        ...

    @property
    @abstractmethod
    def virtual_fields_to_reload_on_refresh(self) -> abc.Mapping[str, "VirtualField"]:
        ...

    @property
    @abstractmethod
    def virtual_fields_to_delete_on_save(self) -> abc.Mapping[str, "VirtualField"]:
        ...

    @property
    @abstractmethod
    def virtual_fields_to_reload_on_save(self) -> abc.Mapping[str, "VirtualField"]:
        ...


class ImplementsVirtualFields(ABC, m.Model if TYPE_CHECKING else object):
    _implements_virtual_fields_: Final = True
    _meta: ClassVar["VirtualizedOptions[Self]"]

    @classmethod
    def setup(self, cls: type[_T_Model]):
        if not "_implements_virtual_fields_" in cls.__dict__:
            cls._implements_virtual_fields_ = True
            self._setup_refresh_from_db(cls)
            self._setup_save_base(cls)

        self.register(cls)
        return cls

    @classmethod
    def _has_support_in_mro(self, cls: type, attr, check=None):
        check = check or "_supports_virtual_fields_"
        return getattr(_mro_get(cls, attr), check, False)

    @classmethod
    def _set_support_marker(self, obj, value=True, check=None) -> None:
        setattr(obj, check or "_supports_virtual_fields_", value)
        return obj

    @classmethod
    def _setup_refresh_from_db(self, cls: type[_T_Model]):
        if self._has_support_in_mro(cls, "refresh_from_db"):
            return

        _orig = _mro_get(cls, "refresh_from_db")

        @wraps(_orig)
        def impl(self: _T_Model, using=None, fields: list[str] = None):
            nonlocal _orig
            opts, attrs = self._meta, self.__dict__
            concrete = opts.concrete_virtual_fields
            deferred = opts.deferred_virtual_fields
            if fields is None:
                reloads = list(opts.virtual_fields_to_reload_on_refresh)
                for field in opts.virtual_fields_to_delete_on_refresh:
                    field in attrs and delattr(self, field)
            elif concrete or deferred:
                fields, reloads, virtual = list(fields), [], []
                for field in fields:
                    if field in deferred:
                        reloads.append(field)
                        fields.remove(field)
                    elif field in concrete:
                        virtual.append(field)

                if reloads and virtual == fields:
                    fields, reloads = [], reloads + virtual

            _orig(self, using, fields)

            if reloads:
                qs = _db_instance_qs(self, using)
                for name, val in zip(reloads, qs.values_list(*reloads).get()):
                    setattr(self, name, val)

        cls.refresh_from_db = self._set_support_marker(impl)

    @classmethod
    def _setup_save_base(self, cls: type[_T_Model]):
        if self._has_support_in_mro(cls, "save_base"):
            return

        _orig = _mro_get(cls, "save_base")

        @wraps(_orig)
        def impl(
            self: _T_Model,
            raw=False,
            force_insert=False,
            force_update=False,
            using=None,
            update_fields=None,
        ):
            nonlocal _orig
            adding = self._state.adding
            _orig(self, raw, force_insert, force_update, using, update_fields)
            if raw:
                return

            opts, attrs = self._meta, self.__dict__

            if adding:
                deletes = opts.virtual_fields_to_delete_on_add
                reloads = opts.virtual_fields_to_reload_on_add
            else:
                deletes = opts.virtual_fields_to_delete_on_save
                reloads = opts.virtual_fields_to_reload_on_save

            for field in deletes:
                field in attrs and delattr(self, field)

            reloads and self.refresh_from_db(self._state.db, list(reloads))

        cls.save_base = self._set_support_marker(impl)


class VirtualizedModel(m.Model):
    _meta: ClassVar["VirtualizedOptions[Self]"]

    class Meta:
        abstract = True


ImplementsVirtualFields.setup(VirtualizedModel)
