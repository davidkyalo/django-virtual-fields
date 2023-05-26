import datetime
import typing as t
from operator import attrgetter
from random import randint

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models as m
from django.db.models.functions import Concat, Extract, Now
from django.utils import timezone

from virtual_fields.fields import VirtualField

if t.TYPE_CHECKING:
    from typing_extensions import Self


class JSONEncoder(DjangoJSONEncoder):
    pass


class Person(m.Model):
    first_name: str = m.CharField(max_length=100)
    last_name: str = m.CharField(max_length=100)
    dob: datetime.date = m.DateField()
    data = m.JSONField(encoder=JSONEncoder, default=dict)

    full_name: str = VirtualField(
        Concat("first_name", m.Value(" "), "last_name"), m.CharField()
    )

    age: int = VirtualField(
        Extract(Now(), "year") - Extract("dob", "year"), m.IntegerField()
    )

    city = VirtualField("data__city")
    height = VirtualField(
        # m.functions.Cast(
        m.F("data__height"),
        m.FloatField()
        # m.DecimalField(max_digits=9, decimal_places=2)
        # )
    )
    weight = VirtualField(m.functions.Cast(m.F("data__weight"), m.IntegerField()))
    # factor = VirtualField(m.F("age") * m.F("height") + m.F("weight"))

    posts: "m.manager.RelatedManager[Post]"
    likes: "m.manager.RelatedManager[Post]"

    class Meta:
        pass

    def __str__(self: "Self") -> str:
        dct = {
            f.attname: getattr(self, f.attname)  # f.value_to_string(self)
            if hasattr(self, f.attname)
            else f"_N{randint(10, 99)}_"
            for f in [
                self._meta.fields[0],
                *sorted(self._meta.fields[1:], key=attrgetter("attname")),
            ]
            if f.attname in self.__dict__
            # if f.attname not in ("first_name", "last_name")
        }
        return f"{dct}"


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
