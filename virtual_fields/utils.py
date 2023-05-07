import typing as t
from abc import ABC

JSON_PRIMITIVES = type(None), bool, str, int, float, tuple, list, dict


class JsonPrimitive(ABC):
    @classmethod
    def __subclasshook__(cls, sub) -> None:
        if cls is JsonPrimitive:
            if issubclass(sub, JSON_PRIMITIVES):
                return True
        return NotImplemented


if t.TYPE_CHECKING:
    JsonPrimitive = (
        None
        | bool
        | str
        | int
        | float
        | tuple["JsonPrimitive", ...]
        | list["JsonPrimitive"]
        | dict[str, "JsonPrimitive"]
    )
