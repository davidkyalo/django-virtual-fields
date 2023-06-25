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
        "slug",
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
        "slug",
        # "author",
        # "author_dob",
        "authored_by",
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
        "slug",
        "type",
        "authored_by",
        "author_dob",
        "num_likes",
        "num_comments",
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
        "slug",
        "created_at",
        "authored_by",
        "author_dob",
        "num_likes",
        "num_comments",
    ]


@admin.register(Article)
class ArticleAdmin(PostAdmin):
    list_display = [
        "id",
        "title",
        "writer",
        "slug",
        "writer_slug",
        # "author_dob",
        "authored_by",
        "published_at",
        "created_at",
        "parent_id",
    ]
    list_select_related = ["writer"]

    fields = [
        "id",
        "title",
        "writer",
        "writer_slug",
        "slug",
        "type",
        # "authored_by",
        # "author_dob",
        # "num_likes",
        # "num_comments",
        "published_at",
        "created_at",
        "content",
        "data",
    ]
    readonly_fields = PostAdmin.readonly_fields + ["writer", "writer_slug"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).filter()


@admin.register(Comment)
class CommentAdmin(PostAdmin):
    pass


# for i, (pk, title) in enumerate(qs.values_list("pk", "title").all()):
#     if qs.filter(pk=pk).update(slug=slugify(title)):
#         print(f"{i:04} Ok ...")
#     else:
#         print(f"{i:04} Err ...")

# for _ in range(1):
#     [Article.create() for _ in range(5)]
#     [Comment.create() for _ in range(20)]
