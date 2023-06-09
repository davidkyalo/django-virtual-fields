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

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).select_virtual("name", "bmi_cat")


class PostAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "title",
        "author",
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
