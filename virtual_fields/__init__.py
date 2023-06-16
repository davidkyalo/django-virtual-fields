from . import _compat  # type: ignore
from .fields import ForeignVirtualField, VirtualField

__all__ = [
    "VirtualField",
    "ForeignVirtualField",
]
