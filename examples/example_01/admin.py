from typing import Any

from django.contrib import admin
from django.db.models.query import QuerySet
from django.http.request import HttpRequest

# Register your models here.
from .models import Article, Comment, Person, Post


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "full_name",
        "city",
        "country",
        "dob",
        "age",
        "height",
        "weight",
        "bmi",
    ]

    search_fields = ["full_name", "city", "bmi"]

    readonly_fields = [
        "id",
        "age",
        "city",
        "name",
        "height",
        "weight",
        "bmi",
    ]
    fields = [
        "id",
        "first_name",
        "last_name",
        "name",
        "dob",
        "age",
        "country",
        "city",
        "height",
        "weight",
        "bmi",
    ]


class PostAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "title",
        "author",
        "author_name",
        "published_at",
        "created_at",
        "parent",
    ]

    search_fields = [
        "title",
        "author__full_name",
    ]


@admin.register(Article)
class ArticleAdmin(PostAdmin):
    pass


@admin.register(Comment)
class CommentAdmin(PostAdmin):
    pass


# [Person.create() for _ in range(20)]
# [Post.create() for _ in range(200)]
