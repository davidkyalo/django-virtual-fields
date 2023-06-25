import typing as t
from collections import abc, defaultdict

import pytest as pyt
from django.db import models as m

from tests.test_virtual_fields.models import ExprSource as Src
from tests.test_virtual_fields.models import T_Func as _T_Fn
from tests.test_virtual_fields.models import (
    TestModel,
    TestModel_A,
    TestModel_B,
    TestModel_C,
)
from virtual_fields import (
    VirtualForeignKey,
    VirtualManyToManyField,
    VirtualOneToOneField,
)

_VT = t.TypeVar("_VT", covariant=True)
_FT = t.TypeVar("_FT", bound=m.Field, covariant=True)


pytestmark = [
    pyt.mark.django_db,
]


class test__VirtualForeignKey:
    field_types = (
        m.IntegerField,
        m.CharField,
        m.DateField,
        m.DateTimeField,
        m.TimeField,
    )
    all_sources = (Src.FIELD,)

    source_support: t.ClassVar = defaultdict(lambda: True)

    @pyt.fixture(
        name="field",
        params=field_types,
        ids=[f.__name__ for f in field_types],
    )
    def field_fixture(self, request: pyt.FixtureRequest):
        return request.param

    @pyt.fixture(name="source", params=all_sources)
    def source_fixture(self, request: pyt.FixtureRequest, field: type):
        if self.source_support[(source := request.param), field]:
            return source
        pyt.skip(f"{field.__name__!r} does not support source {source!r}")

    def test_basic(
        self,
        factory: _T_Fn[_VT],
        define: _T_Fn[type[TestModel]],
    ):
        Parent = define()
        name = Parent.field_name
        Child = define(
            TestModel_B,
            parent=VirtualForeignKey(Parent, name, "test", related_name="children"),
        )

        parent_0: Parent
        parent_1: Parent
        children_0: "m.manager.RelatedManager[Child]"
        children_1: "m.manager.RelatedManager[Child]"

        p_qs, c_qs = Parent.objects.all(), Child.objects.all()
        key_0, key_1 = factory(), factory()
        parent_0, parent_1 = p_qs.create(value=key_0), p_qs.create(value=key_1)
        child_0_0, child_0_1 = c_qs.create(value=key_0), c_qs.create(value=key_0)
        child_1_0, child_1_1 = c_qs.create(value=key_1), c_qs.create(value=key_1)

        assert child_0_0.parent == parent_0 == child_0_1.parent
        assert child_1_0.parent == parent_1 == child_1_1.parent

        children_sets = [
            (parent_0.children, parent_1.children),
            (c_qs.filter(parent=key_0), c_qs.filter(parent=key_1)),
        ]
        for children_0, children_1 in children_sets:
            assert {*children_0.all()} == {child_0_0, child_0_1}
            assert {*children_1.all()} == {child_1_0, child_1_1}


class test__VirtualOneToOneField:
    field_types = (
        m.IntegerField,
        m.CharField,
        m.DateField,
        m.DateTimeField,
        m.TimeField,
    )
    all_sources = (Src.FIELD,)

    source_support: t.ClassVar = defaultdict(lambda: True)

    @pyt.fixture(
        name="field",
        params=field_types,
        ids=[f.__name__ for f in field_types],
    )
    def field_fixture(self, request: pyt.FixtureRequest):
        return request.param

    @pyt.fixture(name="source", params=all_sources)
    def source_fixture(self, request: pyt.FixtureRequest, field: type):
        if self.source_support[(source := request.param), field]:
            return source
        pyt.skip(f"{field.__name__!r} does not support source {source!r}")

    def test_basic(
        self,
        factory: _T_Fn[_VT],
        define: _T_Fn[type[TestModel]],
    ):
        Parent = define()
        name = Parent.field_name
        Child = define(
            TestModel_B,
            parent=VirtualOneToOneField(Parent, name, "test", related_name="child"),
        )

        p_qs, c_qs = Parent.objects.all(), Child.objects.all()
        key_0, key_1 = factory(), factory()
        parent_0, parent_1 = p_qs.create(value=key_0), p_qs.create(value=key_1)
        child_0, child_1 = c_qs.create(value=key_0), c_qs.create(value=key_1)

        assert child_0.parent == parent_0
        assert child_1.parent == parent_1

        assert child_0 == parent_0.child
        assert child_1 == parent_1.child


class test__VirtualManyToManyField:
    field_types = (
        m.IntegerField,
        m.CharField,
        m.DateField,
        m.DateTimeField,
        m.TimeField,
    )
    all_sources = (Src.FIELD,)

    source_support: t.ClassVar = defaultdict(lambda: True)

    @pyt.fixture(
        name="field",
        params=field_types,
        ids=[f.__name__ for f in field_types],
    )
    def field_fixture(self, request: pyt.FixtureRequest):
        return request.param

    @pyt.fixture(name="source", params=all_sources)
    def source_fixture(self, request: pyt.FixtureRequest, field: type):
        if self.source_support[(source := request.param), field]:
            return source
        pyt.skip(f"{field.__name__!r} does not support source {source!r}")

    def test_basic(
        self,
        factory: _T_Fn[_VT],
        define: _T_Fn[type[TestModel]],
    ):
        A = define(TestModel_A)
        B = define(TestModel_B)
        name, name_2 = A.field_name, A.field_name_2
        Joint = define(
            TestModel_C,
            a=VirtualForeignKey(A, name, name),
            b=VirtualForeignKey(B, name_2, name),
        )

        rel = VirtualManyToManyField(A, Joint, ["a", "b"], related_name="rel")
        B.add_to_class("rel", rel)
        qs_a, qs_b, qs_j = A.objects.all(), B.objects.all(), Joint.objects.all()

        key_0, key_1, key_2 = factory(), factory(), factory()

        a_0, a_1, a_2 = (qs_a.create(value=v) for v in (key_0, key_1, key_2))
        b_0, b_1, b_2 = (qs_b.create(value=v) for v in (key_0, key_1, key_2))

        j_0, j_1, j_2, j_3, j_4, j_5 = (
            qs_j.create(value=v, value_2=v2)
            for v, v2 in [
                (key_0, key_0),
                (key_0, key_1),
                (key_1, key_1),
                (key_1, key_2),
                (key_2, key_2),
                (key_2, key_0),
            ]
        )

        # assert 0
        # _rels = [
        #     # (a_0, (b_0, b_1)),
        #     # (a_1, (b_1, b_2)),
        #     # (a_2, (b_2, b_0)),
        #     (b_0, (a_0, a_2)),
        #     (b_1, (a_0, a_1)),
        #     (b_2, (a_1, a_2)),
        # ]
        # for obj, expected in _rels:
        #     rel_objs = {*obj.rel.all()}
        #     assert rel_objs == {*expected}
