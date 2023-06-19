from typing import TYPE_CHECKING

from django.db import models as m

if TYPE_CHECKING:
    from .models import _T_Model


def _db_instance_qs(
    obj: "_T_Model | type[_T_Model]", using=None, pk=None, *, filter=None
):
    hints = None
    if isinstance(obj, m.Model):
        state = obj._state
        if using is None:
            using = state.db
        if pk is None and not state.adding:
            hints = {"instance": obj}
            if filter is not False:
                pk = obj.pk
    man = obj._meta.base_manager
    qs: m.Manager["_T_Model"] = man.db_manager(using, hints=hints)
    return qs.filter(pk=obj.pk) if pk is not None else qs.all()
