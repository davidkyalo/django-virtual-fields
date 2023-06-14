from typing import Any

from django.contrib import admin
from django.db import models as m
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
        # "country",
        "dob",
        "age",
        "height",
        "weight",
        "bmi",
        "bmi_cat",
    ]

    search_fields = ["full_name", "city", "bmi"]

    readonly_fields = [
        "id",
        "age",
        "city",
        "name",
        "height",
        "weight",
        "data",
        "bmi",
        "bmi_cat",
    ]
    fields = [
        "id",
        "first_name",
        "last_name",
        "data",
        "dob",
        "age",
        "country",
        "city",
        "height",
        "weight",
        "bmi",
        "bmi_cat",
        "name",
    ]

    ordering = ["age", "name"]

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request)  # .select_virtual("name", "bmi_cat")


class PostAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "title",
        # "author",
        "published_at",
        "created_at",
        "parent_id",
    ]

    search_fields = [
        "title",
        "authored_by",
    ]
    fields = [
        "id",
        "title",
        "type",
        "authored_by",
        "author_dob",
        "published_at",
        "created_at",
        "content",
        "data",
        # "parent",
        # "author",
        # "likes",
    ]

    readonly_fields = [
        "id",
        "created_at",
        "authored_by",
        "author_dob",
    ]


@admin.register(Article)
class ArticleAdmin(PostAdmin):
    pass


@admin.register(Comment)
class CommentAdmin(PostAdmin):
    pass
