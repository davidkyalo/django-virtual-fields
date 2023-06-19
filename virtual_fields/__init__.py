from . import _compat

_compat._install()

from .fields import VirtualField

__all__ = [
    "VirtualField",
]
