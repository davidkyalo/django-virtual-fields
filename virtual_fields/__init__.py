from . import _compat

_compat._install()

from .fields import VirtualField
from .related import VirtualForeignKey, VirtualManyToManyField, VirtualOneToOneField

__all__ = [
    "VirtualField",
    "VirtualForeignKey",
    "VirtualOneToOneField",
    "VirtualManyToManyField",
]
