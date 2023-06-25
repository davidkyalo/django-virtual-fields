import typing as t  # type: ignore

from . import fields, related

__all__ = [
    "VirtualField",
    "VirtualForeignKey",
    "VirtualOneToOneField",
    "VirtualManyToManyField",
]

class VirtualField(fields.VirtualField[fields._T_Field]):
    pass

class VirtualForeignKey(related.VirtualForeignKey):
    pass

class VirtualOneToOneField(related.VirtualOneToOneField):
    pass

class VirtualManyToManyField(related.VirtualManyToManyField):
    pass
