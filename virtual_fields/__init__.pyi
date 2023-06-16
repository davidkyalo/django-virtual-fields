import typing as t  # type: ignore

from . import fields

__all__ = [
    "VirtualField",
    "ForeignVirtualField",
]

class VirtualField(fields.VirtualField[fields._T_Field]):
    pass

class ForeignVirtualField(fields.ForeignVirtualField[fields._T_Field]):
    pass
