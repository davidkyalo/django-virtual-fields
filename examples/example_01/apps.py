from django.apps import AppConfig


class Example01Config(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = __package__
