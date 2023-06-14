import typing as t  # type: ignore

from . import fields

__all__ = [
    "VirtualField",
    "RelatedVirtualField",
]

class VirtualField(fields.VirtualField[fields._T_Field]):
    pass

class RelatedVirtualField(fields.RelatedVirtualField[fields._T_Field]):
    pass
