import datetime
import typing as t
from decimal import Decimal
from operator import attrgetter
from pprint import pformat
from random import randint

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models as m
from django.db.models.fields.json import KT
from django.db.models.functions import Concat, Extract, Now
from django.db.models.query import QuerySet
from django.utils import timezone

from examples.faker import faker, ufaker
from virtual_fields import VirtualField

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
    dob: datetime.date = m.DateField("date of birth")
    data = m.JSONField(encoder=JSONEncoder, blank=True, default=_fake_data)

    full_name: str = VirtualField[m.CharField](
        Concat("first_name", m.Value(" "), "last_name")
    )
    yob: int = VirtualField("dob__year", verbose_name="year of birth")
    age: int = VirtualField[m.IntegerField](Extract(Now(), "year") - m.F("yob"))

    name = VirtualField("full_name", m.Value(""), cache=False)

    @name.getter
    def _get_name(self):
        return self.full_name

    @name.setter
    def _set_name(self, val):
        self.first_name, _, self.last_name = f"{val}".partition(" ")

    @name.deleter
    def _del_name(self):
        pass

    country = VirtualField[m.CharField](
        KT("data__country"), default=ufaker.country, defer=True, editable=True
    )
    city = VirtualField[m.CharField](KT("data__city"), defer=True, editable=True)
    height = VirtualField[m.DecimalField](
        KT("data__height"), decimal_places=2, max_digits=8, cast=True
    )
    weight = VirtualField[m.IntegerField]("data__weight", cast=True)
    bmi = VirtualField(
        m.F("weight") / m.functions.Power(m.F("height"), 2),
        output_field=m.DecimalField(max_digits=12, decimal_places=3),
        cast=True,
        verbose_name="body mass index",
    )

    bmi_cat = VirtualField(defer=True)

    @bmi_cat.expression
    def bmi_cat(cls):
        return m.Case(
            m.When(bmi__lt=18.5, then=m.Value("Underweight")),
            m.When(bmi__lt=25, then=m.Value("Normal weight")),
            m.When(bmi__lt=30, then=m.Value("Overweight")),
            default=m.Value("Obesity"),
        )

    # likes = VirtualField[m.IntegerField](m.Count("liked"))
    posts: "m.manager.RelatedManager[Post]"
    liked: "m.manager.RelatedManager[Post]"

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
        data = data or {}
        faker.pybool() and data.setdefault("country", faker.country())
        return qs.create(
            **{
                "first_name": faker.first_name(),
                "last_name": faker.last_name(),
                "dob": faker.date_object(),
                "data": {
                    "city": faker.city(),
                    "height": faker.pyfloat(None, 3, True, 1, 3),
                    "weight": faker.pyint(40, 120, 5),
                    **(data or {}),
                },
                **kw,
            }
        )


class PostType(m.TextChoices):
    article = "article"
    comment = "comment"


class PostManager(m.Manager):
    def get_queryset(self) -> QuerySet:
        return super().get_queryset().select_related("author")


class Post(m.Model):
    class Meta:
        default_manager_name = "objects"

    objects = PostManager()
    title: str = m.CharField(max_length=255)
    content: str = m.TextField()
    type: PostType = m.CharField(choices=PostType.choices, max_length=32)
    published_at: datetime.datetime = m.DateTimeField(null=True, default=timezone.now)
    created_at: datetime.datetime = m.DateTimeField(auto_now_add=True)

    data = m.JSONField(encoder=JSONEncoder, default=dict)

    parent = m.ForeignKey("self", m.CASCADE, null=True, related_name="children")
    author: Person = m.ForeignKey(Person, m.CASCADE, related_name="posts")
    likes: "m.manager.RelatedManager[Person]" = m.ManyToManyField(
        Person, related_name="liked"
    )

    children: "m.manager.RelatedManager[Post]"

    # authored_by = VirtualField[m.CharField]("author__full_name", defer=True)

    # @authored_by.expression
    # def authored_by_expr(cls):
    #     return m.Subquery(
    #         Person.objects.filter(pk=m.OuterRef("author_id")).values_list(
    #             "full_name", flat=True
    #         )[:1]
    #     )

    @classmethod
    def create(cls, qs=None, /, type: PostType = None, **kw):
        ppl = [*Person.objects.all()] or [Person.create() for x in range(10)]
        if qs is None:
            qs = cls._default_manager

        if type is None:
            if cls is Post:
                ats = Post.objects.filter(type=PostType.article).count()
                type = [*PostType][+faker.pybool(80 if ats > 5 else 40 if ats else 0)]
            else:
                type = cls._post_type_

        if not any(k in kw for k in ("author", "author_id")):
            kw["author"] = p = faker.random_element(ppl)
            ppl.remove(p)

        if type == PostType.comment and "parent" not in kw:
            kw["parent"] = pr = Post.objects.all()[
                faker.random_int(0, Post.objects.count() - 1)
            ]
            kw["published_at"] = pr.published_at + datetime.timedelta(
                seconds=faker.random_int(180, 3600 * 72)
            )

        obj = qs.create(
            **{
                "title": faker.sentence(faker.random_int(3, 6))[:255],
                "type": type,
                "content": "\n\n".join(
                    ufaker.paragraph(faker.random_int(3, 6))
                    for _ in range(faker.random_int(2, 10))
                ),
                "published_at": faker.date_time_this_year(),
                **kw,
            }
        )

        obj.likes.add(
            *faker.random_choices(ppl, faker.random_int(0, int(len(ppl) / 2))),
        )

        return obj


class Article(Post):
    _post_type_ = PostType.article

    class Meta:
        proxy = True


class Comment(Post):
    _post_type_ = PostType.comment

    class Meta:
        proxy = True
