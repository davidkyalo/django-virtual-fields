#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    argv = sys.argv
    s_opt = "--settings"
    aliases = {
        "tests": "tests.test_virtual_fields.settings",
        "examples": "examples.settings",
    }
    if arg := s_opt in argv and argv[i := argv.index(s_opt) + 1]:
        if mod := aliases.get(arg.rstrip("-")):
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", mod)
            argv[i - 1 : i + 1] = [] if arg[-1] == "-" else [s_opt, mod]

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "examples.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(argv)


if __name__ == "__main__":
    main()
