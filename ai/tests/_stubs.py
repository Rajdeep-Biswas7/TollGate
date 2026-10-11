"""Minimal stand-ins for pydantic and httpx so the test-suite also runs on a bare Python install.

Imported first by every test module. If the real packages are installed, nothing is stubbed and
the tests run against the real libraries.
"""
from __future__ import annotations

import sys
import types

try:
    import pydantic  # noqa: F401
except ImportError:  # --------------------------------------------------------- pydantic stub
    m = types.ModuleType("pydantic")

    class ValidationError(Exception):
        def __init__(self, errs):
            super().__init__(str(errs))
            self._errs = errs

        def errors(self):
            return self._errs

    class _FieldInfo:
        def __init__(self, default=..., **kw):
            self.default, self.kw = default, kw

    def Field(default=..., **kw):
        return _FieldInfo(default, **kw)

    _TYPES = {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}

    class BaseModel:
        _fields: dict = {}

        def __init_subclass__(cls, **kw):
            cls._fields = {}
            for name, ann in getattr(cls, "__annotations__", {}).items():
                default = cls.__dict__.get(name, ...)
                info = default if isinstance(default, _FieldInfo) else _FieldInfo(default)
                cls._fields[name] = (ann, info)

        def __init__(self, **kw):
            self.__dict__.update(kw)

        @classmethod
        def model_validate(cls, data):
            errs, out = [], {}
            for name, (ann, info) in cls._fields.items():
                if name not in data:
                    if info.default is ...:
                        errs.append({"loc": (name,), "msg": "Field required"})
                        continue
                    out[name] = info.default
                    continue
                v = data[name]
                if isinstance(v, str):
                    if "min_length" in info.kw and len(v) < info.kw["min_length"]:
                        errs.append({"loc": (name,), "msg": f"String should have at least {info.kw['min_length']} characters"})
                    if "max_length" in info.kw and len(v) > info.kw["max_length"]:
                        errs.append({"loc": (name,), "msg": "String too long"})
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if "ge" in info.kw and v < info.kw["ge"]:
                        errs.append({"loc": (name,), "msg": f"Input should be greater than or equal to {info.kw['ge']}"})
                    if "le" in info.kw and v > info.kw["le"]:
                        errs.append({"loc": (name,), "msg": f"Input should be less than or equal to {info.kw['le']}"})
                out[name] = v
            if errs:
                raise ValidationError(errs)
            return cls(**out)

        def model_dump(self):
            return dict(self.__dict__)

        @classmethod
        def model_json_schema(cls):
            props, req = {}, []
            for name, (ann, info) in cls._fields.items():
                a = str(ann)
                if a.startswith("list"):
                    p = {"type": "array", "items": {"type": _TYPES.get(a[5:-1], "string")}}
                else:
                    p = {"type": _TYPES.get(a, "string")}
                p["title"] = name.title()
                if info.default is not ...:
                    p["default"] = info.default
                else:
                    req.append(name)
                if "description" in info.kw:
                    p["description"] = info.kw["description"]
                for k_src, k_dst in (("min_length", "minLength"), ("max_length", "maxLength"), ("ge", "minimum"), ("le", "maximum")):
                    if k_src in info.kw:
                        p[k_dst] = info.kw[k_src]
                props[name] = p
            schema = {"properties": props, "title": cls.__name__, "type": "object"}
            if req:
                schema["required"] = req
            return schema

    def field_validator(*a, **k):
        return lambda f: f

    m.BaseModel, m.Field, m.ValidationError, m.field_validator = BaseModel, Field, ValidationError, field_validator
    sys.modules["pydantic"] = m

try:
    import httpx  # noqa: F401
except ImportError:  # --------------------------------------------------------- httpx stub
    h = types.ModuleType("httpx")

    class HTTPError(Exception):
        pass

    class TimeoutException(HTTPError):
        pass

    class AsyncClient:  # only used as a type
        is_closed = False

    class Response:  # only used as a type
        pass

    h.HTTPError, h.TimeoutException, h.AsyncClient, h.Response = HTTPError, TimeoutException, AsyncClient, Response
    h.Timeout = lambda *a, **k: (a, k)
    h.Limits = lambda *a, **k: (a, k)
    sys.modules["httpx"] = h
