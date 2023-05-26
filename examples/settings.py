"""
Django settings for example project.

Generated by 'django-admin startproject' using Django 4.1.4.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.1/ref/settings/
"""

from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = (Path(__file__) / "../../").resolve()

env = environ.Env(
    DEBUG=(bool, False),
    DATABASE_VENDOR=(str, None),
)

environ.Env.read_env(BASE_DIR / ".env")

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-5trb!_%h&82&2k1&4mx^60g!c__l(8&f1@j)@e2txgrg8ea*c#"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

ALLOWED_HOSTS = ["*"]


LOG_LEVEL = "DEBUG"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "formatters": {
        "django.server": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[{server_time}] {message}",
            "style": "{",
        },
        "verbose": {
            "format": "[{asctime}] {name} [{levelname}]: {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{levelname}]: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "mail_admins"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db": {
            "handlers": ["console", "mail_admins"],
            "level": LOG_LEVEL,
            "propagate": True,
        },
        "django.server": {
            "handlers": ["console", "mail_admins"],
            "level": "INFO",
            "propagate": False,
        },
        "virtual_fields": {
            "handlers": ["console", "mail_admins"],
            "level": LOG_LEVEL,
            "propagate": True,
        },
        "examples": {
            "handlers": ["console", "mail_admins"],
            "level": LOG_LEVEL,
            "propagate": True,
        },
        "faker": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
    },
}

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "polymorphic",
    "virtual_fields",
    "examples",
    "examples.example_01",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ROOT_URLCONF = "examples.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "examples.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases

DATABASES_BY_VENDOR: dict = {
    "sqlite": env.db_url_config("sqlite:////tmp/test-sqlite.db"),
    "mysql": env.db_url_config("mysql://root:root@localhost/test_db"),
    "pgsql": env.db_url_config("postgres://root:root@localhost/test_db"),
    **env.dict("DATABASES", {"value": env.db_url_config}, {}),
}
DATABASE_VENDOR = env("DATABASE_VENDOR") or next(iter(DATABASES_BY_VENDOR))
DATABASES = dict(DATABASES_BY_VENDOR)
DATABASES["default"] = DATABASES.pop(DATABASE_VENDOR)


tox_env: str | None = env("TOX_ENV_NAME", default=None)
if tox_env:
    for k in DATABASES_BY_VENDOR:
        tox_env = tox_env.replace(f"-{k}", "")
    tox_env = tox_env.strip("-_.").replace("--", "-").replace(".", "").replace("-", "_")
    DATABASES["default"]["NAME"] = f"{DATABASES['default']['NAME']}__{tox_env}"


# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    # {
    #     "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    # },
    # {
    #     "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    # },
    # {
    #     "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    # },
    # {
    #     "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    # },
]


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = False


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = "static/"

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
