# Django Virtual Fields


[![PyPi version][pypi-image]][pypi-link]
[![Supported Python versions][pyversions-image]][pyversions-link]
[![Build status][ci-image]][ci-link]
[![Coverage status][codecov-image]][codecov-link]

_Django Virtual Fields_ enables you to define model `fields` from computed database `expressions`.

### Documentation

Full documentation is available [here][docs-link].

### Installation 

Install from [PyPi](https://pypi.org/project/django-virtual-fields/)
    
```
pip install django-virtual-fields
```

## Quick Start

Here's an example `model.py`.

```python
from django.db import models as m
from django.db.models.fields.json import KT
from django.db.models.functions import Concat, Extract, Now

# 
from virtual_fields import VirtualField

class Person(m.Model):
    # Model fields
    first_name: str = m.CharField(max_length=100)
    last_name: str = m.CharField(max_length=100)
    dob: "date" = m.DateField("date of birth")
    extra_data: dict = m.JSONField(default=dict(city="My City"))

    # Virtual fields
    yob: int = VirtualField("dob__year", verbose_name="year of birth")
    age: int = VirtualField(Extract(Now(), "year") - m.F("yob"), defer=False)

    city: str = VirtualField[m.CharField](KT("extra_data__city"))

    full_name: str = VirtualField[m.CharField]()
    @full_name.expression
    def full_name_expressions(cls):
        return Concat("first_name", Value(" "), "last_name")

```



[docs-link]: https://davidkyalo.github.io/django-virtual-fields/
[pypi-image]: https://img.shields.io/pypi/v/django-virtual-fields.svg?color=%233d85c6
[pypi-link]: https://pypi.python.org/pypi/django-virtual-fields
[pyversions-image]: https://img.shields.io/pypi/pyversions/django-virtual-fields.svg
[pyversions-link]: https://pypi.python.org/pypi/django-virtual-fields
[ci-image]: https://github.com/davidkyalo/django-virtual-fields/actions/workflows/workflow.yaml/badge.svg?event=push&branch=master
[ci-link]: https://github.com/davidkyalo/django-virtual-fields/actions?query=workflow%3ACI%2FCD+event%3Apush+branch%3Amaster
[codecov-image]: https://codecov.io/gh/davidkyalo/django-virtual-fields/branch/master/graph/badge.svg
[codecov-link]: https://codecov.io/gh/davidkyalo/django-virtual-fields

