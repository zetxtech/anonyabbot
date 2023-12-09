import asyncio
from datetime import timedelta
import enum
import inspect
import re
from typing import Any, Coroutine, Iterable, Union
from datetime import timedelta

class _DefaultType:
    def __new__(cls):
        return Def

    def __reduce__(self):
        return (_DefaultType, ())

    def __bool__(self):
        return False


Def = object.__new__(_DefaultType)

class AsyncTaskPool:
    """A async task pool, which can dynamically add and wait task."""

    def __init__(self):
        self.waiter = asyncio.Condition()
        self.tasks = []

    def add(self, coro: Coroutine):
        async def wrapper():
            task = asyncio.ensure_future(coro)
            await asyncio.wait([task])
            async with self.waiter:
                self.waiter.notify()
                return await task

        t = asyncio.create_task(wrapper())
        t.set_name(coro.__name__)
        self.tasks.append(t)
        return t

    async def as_completed(self, infinite=False):
        for t in self.tasks:
            if t.done():
                yield t
                self.tasks.remove(t)
        while self.tasks or infinite:
            async with self.waiter:
                await self.waiter.wait()
                for t in self.tasks[:]:
                    if t.done():
                        yield t
                        self.tasks.remove(t)

    async def wait(self, infinite=False):
        results = []
        async for t in self.as_completed(infinite=infinite):
            results.append(t.result())
        return results


def remove_prefix(text: str, prefix: str):
    """Remove prefix from the begining of test."""
    return text[text.startswith(prefix) and len(prefix) :]


def walk(l: Iterable[Iterable]):
    """Iterate over a irregular n-dimensional list."""
    for el in l:
        if isinstance(el, Iterable) and not isinstance(el, (str, bytes)):
            yield from flatten(el)
        else:
            yield el


def flatten(l: Iterable[Iterable]):
    """Flatten a irregular n-dimensional list to a 1-dimensional list."""
    return type(l)(walk(l))


def flatten2(l: Iterable[Iterable]):
    """Flatten a 2-dimensional list to a 1-dimensional list."""
    return [i for j in l for i in j]


def count(it: Iterable):
    return sum(1 for _ in it)


def truncate_str(text: str, length: int):
    """Truncate a str to a certain length, and the omitted part is represented by "..."."""
    return f"{text[:length + 3]}..." if len(text) > length else text


def truncate_str_reverse(text: str, length: int):
    """Truncate a str to a certain length from the end, and the omitted part is represented by "..."."""
    return f"...{text[- length - 3:]}" if len(text) > length else text


def async_partial(f, *args1, **kw1):
    async def func(*args2, **kw2):
        return await f(*args1, *args2, **kw1, **kw2)

    return func


def parse_timedelta(time_str):
    """Parse a time string e.g. '2h 13m' or '1.5d' into a timedelta object."""
    regex = re.compile(
        r"^((?P<weeks>[\.\d]+?)w)? *"
        r"^((?P<days>[\.\d]+?)d)? *"
        r"((?P<hours>[\.\d]+?)h)? *"
        r"((?P<minutes>[\.\d]+?)m)? *"
        r"((?P<seconds>[\.\d]+?)s?)?$"
    )
    parts = regex.match(time_str)
    assert (
        parts is not None
    ), """Could not parse any time information from '{}'.
    Examples of valid strings: '8h', '2d 8h 5m 2s', '2m4.3s'""".format(
        time_str
    )
    time_params = {name: float(param) for name, param in parts.groupdict().items() if param}
    return timedelta(**time_params)


def to_iterable(var: Union[Iterable, Any]):
    """
    Turn any variable into iterable variable.
    Note:
        None => [].
        Non-iterable var => [var].
        Iterable var => var.
    """
    if var is None:
        return ()
    if isinstance(var, str) or not isinstance(var, Iterable):
        return (var,)
    else:
        return var


def extract(var: Union[Iterable, Any]):
    """Extract variable from iterable of only one element."""
    it = iter(var)
    try:
        v = next(it)
    except StopIteration:
        return None
    else:
        try:
            next(it)
        except StopIteration:
            return v
        else:
            return var


def batch(iterable, n=1):
    """Split a list into multiple list of size n."""
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx : min(ndx + n, l)]


class ProxyBase:
    """
    A proxy class that make accesses just like direct access to __subject__ if not overwriten in the class.
    Attributes defined in class. attrs named in __noproxy__ will not be proxied to __subject__.
    """

    __slots__ = ()

    def __call__(self, *args, **kw):
        return self.__subject__(*args, **kw)

    def hasattr(self, attr):
        try:
            object.__getattribute__(self, attr)
            return True
        except AttributeError:
            return False

    def __getattribute__(self, attr, oga=object.__getattribute__):
        if attr.startswith("__") and attr not in oga(self, "_noproxy"):
            subject = oga(self, "__subject__")
            if attr == "__subject__":
                return subject
            return getattr(subject, attr)
        return oga(self, attr)

    def __getattr__(self, attr, oga=object.__getattribute__):
        if attr == "hasattr" or self.hasattr(attr):
            return oga(self, attr)
        else:
            return getattr(oga(self, "__subject__"), attr)

    @property
    def _noproxy(self, oga=object.__getattribute__):
        base = oga(self, "__class__")
        for cls in inspect.getmro(base):
            if hasattr(cls, "__noproxy__"):
                yield from cls.__noproxy__

    def __setattr__(self, attr, val, osa=object.__setattr__):
        if attr == "__subject__" or attr in self._noproxy:
            return osa(self, attr, val)
        return setattr(self.__subject__, attr, val)

    def __delattr__(self, attr, oda=object.__delattr__):
        if attr == "__subject__" or hasattr(type(self), attr) and not attr.startswith("__"):
            oda(self, attr)
        else:
            delattr(self.__subject__, attr)

    def __bool__(self):
        return bool(self.__subject__)

    def __getitem__(self, arg):
        return self.__subject__[arg]

    def __setitem__(self, arg, val):
        self.__subject__[arg] = val

    def __delitem__(self, arg):
        del self.__subject__[arg]

    def __getslice__(self, i, j):
        return self.__subject__[i:j]

    def __setslice__(self, i, j, val):
        self.__subject__[i:j] = val

    def __delslice__(self, i, j):
        del self.__subject__[i:j]

    def __contains__(self, ob):
        return ob in self.__subject__

    for name in "repr str hash len abs complex int long float iter".split():
        exec("def __%s__(self): return %s(self.__subject__)" % (name, name))

    for name in "cmp", "coerce", "divmod":
        exec("def __%s__(self, ob): return %s(self.__subject__, ob)" % (name, name))

    for name, op in [
        ("lt", "<"),
        ("gt", ">"),
        ("le", "<="),
        ("ge", ">="),
        ("eq", " == "),
        ("ne", "!="),
    ]:
        exec("def __%s__(self, ob): return self.__subject__ %s ob" % (name, op))

    for name, op in [("neg", "-"), ("pos", "+"), ("invert", "~")]:
        exec("def __%s__(self): return %s self.__subject__" % (name, op))

    for name, op in [
        ("or", "|"),
        ("and", "&"),
        ("xor", "^"),
        ("lshift", "<<"),
        ("rshift", ">>"),
        ("add", "+"),
        ("sub", "-"),
        ("mul", "*"),
        ("div", "/"),
        ("mod", "%"),
        ("truediv", "/"),
        ("floordiv", "//"),
    ]:
        exec(
            (
                "def __%(name)s__(self, ob):\n"
                "    return self.__subject__ %(op)s ob\n"
                "\n"
                "def __r%(name)s__(self, ob):\n"
                "    return ob %(op)s self.__subject__\n"
                "\n"
                "def __i%(name)s__(self, ob):\n"
                "    self.__subject__ %(op)s=ob\n"
                "    return self\n"
            )
            % locals()
        )

    del name, op

    def __index__(self):
        return self.__subject__.__index__()

    def __rdivmod__(self, ob):
        return divmod(ob, self.__subject__)

    def __pow__(self, *args):
        return pow(self.__subject__, *args)

    def __ipow__(self, ob):
        self.__subject__ **= ob
        return self

    def __rpow__(self, ob):
        return pow(ob, self.__subject__)


class Proxy(ProxyBase):
    def __init__(self, val):
        self.set(val)

    def set(self, val):
        self.__subject__ = val

class FuncProxy(ProxyBase):
    __noproxy__ = ("_func", "_args", "_kw")
    
    def __init__(self, func, *args, **kw):
        self.set(func, *args, **kw)

    def set(self, func, *args, **kw):
        self._func = func
        self._args = args
        self._kw = kw
        
    @property
    def __subject__(self):
        return self._func(*self._args, **self._kw)