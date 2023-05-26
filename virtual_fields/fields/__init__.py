from logging import getLogger

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
    empty_strings_allowed = False
    is_function = True
    description = _("A virtual field. Uses query annotations to return computed value.")
    output_field: m.Field
    expression: m.expressions.Combinable | m.Q | str
    defer: bool

    descriptor_class = VirtualFieldDescriptor

    def __init__(
        self,
        expression: m.expressions.Combinable | m.Q | str = None,
        output_field=None,
        defer: bool = None,
        **kwargs,
    ):
        self.output_field = output_field
        self.defer = defer is not False
        self.expression = expression

        super().__init__(**kwargs)

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
        expr = m.ExpressionWrapper(expr, self.output_field)
        expr.target = self
        return expr

    def get_internal_type(self):
        logger.error(f"\n---> {self._model_name}.get_internal_type()")
        return "VirtualField"

    def db_type(self, connection):
        logger.error(f"\n---> {self._model_name}.db_type({connection})")
        return None

    def validate(self, value, model_instance):
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
        qs = m.QuerySet(model=self.model)
        qs._fields = {
            f.attname
            for f in self.model._meta.fields
            if not isinstance(f, VirtualField)
        }
        qs = qs.alias(**{self.attname: self.final_expression})
        # qs = qs.annotate(**{self.attname: self.final_expression}).order_by(self.attname)
        return qs.query.annotations[self.attname]

    # def get_col(self, alias, output_field=None):
    #     logger.error(
    #         f"\n---> {self._model_name}.get_col({alias!r}, {output_field}) "
    #         f"\n    -> {self.cached_col}"
    #     )
    #     return self.cached_col

    # def get_col(self, alias, output_field=None):
    #     val = super().get_col(alias, output_field)

    #     logger.error(
    #         f"\n---> {self}.get_col({alias!r}, {output_field}) " f"\n    -> {val}"
    #     )
    #     return val

    # def get_attname_column(self):
    #     logger.error(f"---> {self._model_name}.get_attname_column()")
    #     return self.get_attname(), None
