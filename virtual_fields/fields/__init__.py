from logging import getLogger
from typing import overload

from django.db import models as m
from django.db.models.query_utils import DeferredAttribute
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

__all__ = [
    "VirtualField",
]


logger = getLogger(__name__)


class VirtualFieldDescriptor(DeferredAttribute):
    field: "VirtualField"

    def _check_parent_chain(self, instance: m.Model):
        if (
            val := super()._check_parent_chain(instance)
        ) is None and not instance._state.adding:
            qs: m.QuerySet = instance.__class__._default_manager
            val = qs.values_list(self.field.attname, flat=True).get(pk=instance.pk)
        return val


class VirtualField(m.Field):
    description = _("A virtual field. Uses query annotations to return computed value.")
    expression: m.expressions.Combinable | m.Q | str
    output_field: m.Field = None
    defer: bool = False

    descriptor_class = VirtualFieldDescriptor

    _field_init_default_ = {
        "editable": False,
        "serialize": False,
    }

    @overload
    def __init__(
        self,
        expressions: m.expressions.Combinable | m.Q | str = None,
        output_field: m.Field = None,
        defer: bool | None = None,
        verbose_name: str = None,
        name: str = None,
        max_length: int = None,
        unique: bool = False,
        blank: bool = False,
        null: bool = False,
        db_cast: bool = False,
        db_index: bool = False,
        default=...,
        editable: bool = False,
        serialize: bool = False,
        unique_for_date=None,
        unique_for_month=None,
        unique_for_year=None,
        choices=None,
        help_text="",
        validators=(),
        error_messages=None,
    ):
        ...

    def __init__(
        self,
        expression: m.expressions.Combinable | m.Q | str = None,
        output_field=None,
        defer: bool = None,
        db_cast: bool = None,
        **kwargs,
    ):
        self.expression = expression
        self.output_field = output_field
        self.defer, self.db_cast = defer, db_cast
        super().__init__(**self._field_init_default_ | kwargs)

    @cached_property
    def empty_strings_allowed(self):
        return o.empty_strings_allowed if (o := self.output_field) else False

    @property
    def _model_name(self):
        vals = []
        if hasattr(self, "model"):
            vals.append(self.model._meta.model_name)

        if hasattr(self, "attname"):
            vals.append(self.attname)

        return ".".join(vals)

    @cached_property
    def final_expression(self):
        if isinstance(expr := self.expression, str):
            expr = m.F(f"{expr}")

        out = self.output_field
        if self.db_cast:
            expr = m.functions.Cast(expr, out)
        else:
            expr = m.ExpressionWrapper(expr, self.output_field)
        expr.target = self
        return expr

    def get_internal_type(self):
        return "VirtualField"

    def db_type(self, connection):
        return None

    def select_format(self, compiler, sql, params):
        """
        Custom format for select clauses. For example, GIS columns need to be
        selected as AsText(table.col) on MySQL as the table.col data can't be
        used by Django.
        """
        _sql, _params = super().select_format(compiler, sql, params)
        return _sql, _params

    def validate(self, value, model_instance):
        super().validate(value, model_instance)
        if field := self.output_field:
            return field.validate(value, model_instance)

    def formfield(self, **kwargs):
        if field := self.output_field:
            return field.formfield(**kwargs)

    def contribute_to_class(self, cls, name, private_only=None):
        super().contribute_to_class(cls, name, private_only is not False)
        setattr(cls, self.attname, self.descriptor_class(self))

    @cached_property
    def cached_col(self):
        name, qs = self.name, m.QuerySet(model=self.model)
        qs._fields = {f.name for f in self.model._meta.fields if f.name != name}
        qs = qs.annotate(**{name: self.final_expression})
        rv = qs.query.annotations[name]
        return rv

    def get_attname_column(self):
        """Sets column to `None` for deferred fields to prevent selection."""
        attname, column = super().get_attname_column()
        return attname, None if self.defer else column
