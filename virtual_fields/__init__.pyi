import typing as t  # type: ignore

from . import fields

__all__ = [
    "VirtualField",
]

class VirtualField(fields.VirtualField[fields._T_Field]):
    pass
