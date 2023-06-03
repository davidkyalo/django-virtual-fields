import datetime
import typing as t
from operator import attrgetter
from pprint import pformat
from random import randint

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models as m
from django.db.models.fields.json import KT
from django.db.models.functions import Concat, Extract, Now
from django.utils import timezone

from examples.faker import ufaker
from virtual_fields.fields import VirtualField

if t.TYPE_CHECKING:
    from typing_extensions import Self


class JSONEncoder(DjangoJSONEncoder):
    pass


def _fake_data():
    return {
        "city": ufaker.city(),
        "height": ufaker.pyfloat(None, 3, True, 1, 3),
        "weight": ufaker.pyint(40, 120, 5),
    }


class Person(m.Model):
    first_name: str = m.CharField(max_length=100)
    last_name: str = m.CharField(max_length=100)
    dob: datetime.date = m.DateField()
    data = m.JSONField(encoder=JSONEncoder, blank=True, default=_fake_data)

    name = VirtualField("first_name", defer=True)

    full_name: str = VirtualField(
        Concat("first_name", m.Value(" "), "last_name"), m.CharField()
    )

    age: int = VirtualField(
        Extract(Now(), "year") - Extract("dob", "year"), m.IntegerField()
    )

    city = VirtualField(KT("data__city"), m.CharField(), editable=True)

    height = VirtualField(m.functions.Cast(KT("data__height"), m.FloatField()))

    weight = VirtualField(m.functions.Cast(m.F("data__weight"), m.IntegerField()))
    bmi = VirtualField(
        m.F("weight") / m.functions.Power(m.F("height"), 2),
        m.DecimalField(max_digits=12, decimal_places=3),
        db_cast=True,
        verbose_name="body mass index",
    )
    posts: "m.manager.RelatedManager[Post]"
    likes: "m.manager.RelatedManager[Post]"

    class Meta:
        pass

    def __repr__(self: "Self") -> str:
        dct = {
            f.attname: getattr(self, f.attname)  # f.value_to_string(self)
            if hasattr(self, f.attname)
            else f"_N{randint(10, 99)}_"
            for f in [
                self._meta.fields[0],
                *sorted(self._meta.fields[1:], key=attrgetter("attname")),
            ]
            # if f.attname in self.__dict__
            # if f.attname not in ("first_name", "last_name")
        }
        return f"{self.__class__.__name__}({pformat(dct, 2, 12, 5)})"

    def __str__(self: "Self") -> str:
        return f"{self.first_name}"

    @classmethod
    def create(cls, qs=None, /, *, data=None, **kw):
        qs = cls._default_manager if qs is None else qs
        return qs.create(
            **{
                "first_name": ufaker.first_name(),
                "last_name": ufaker.last_name(),
                "dob": ufaker.date_object(),
                "data": {
                    "city": ufaker.city(),
                    "height": ufaker.pyfloat(None, 3, True, 1, 3),
                    "weight": ufaker.pyint(40, 120, 5),
                    **(data or {}),
                },
                **kw,
            }
        )


class PostType(m.TextChoices):
    article = "article"
    comment = "comment"


class Post(m.Model):
    title: str = m.CharField(max_length=255)
    content: str = m.TextField()
    type: PostType = m.CharField(choices=PostType.choices, max_length=32)
    published_at: datetime.datetime = m.DateTimeField(null=True, default=timezone.now)
    created_at: datetime.datetime = m.DateTimeField(auto_now_add=True)

    data = m.JSONField(encoder=JSONEncoder, default=dict)

    parent = m.ForeignKey("self", m.CASCADE, null=True, related_name="children")
    author: Person = m.ForeignKey(Person, m.CASCADE, related_name="posts")
    likes: Person = m.ManyToManyField(Person, related_name="liked")

    children: "m.manager.RelatedManager[Post]"


class Article(Post):
    class Meta:
        proxy = True


class Comment(Post):
    class Meta:
        proxy = True
