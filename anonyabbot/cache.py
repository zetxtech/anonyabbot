import asyncio
from collections import deque

import dill
from loguru import logger
import redis
import fakeredis

from .config import config
from .utils import Def, ProxyBase

class Cache:
    source = None
    
    def __init__(self, base=None):
        self._base = base
    
    @classmethod
    def get_redis(cls):
        if not cls.source:
            cls.refresh()
        if isinstance(cls.source, redis.StrictRedis):
            return cls.source
        else:
            return None
    
    @classmethod
    def refresh(cls):
        redis_conf = config.get('redis', None)
        if not redis_conf:
            logger.warning('Redis is not configured, and caches will be lost during program restart.')
            cls.source = fakeredis.FakeStrictRedis()
        else:
            cls.source = redis.StrictRedis(
                host = redis_conf.get('host', 'localhost'),
                port = int(redis_conf.get('port', 6379)),
                db = int(redis_conf.get('db', 0)),
                password = redis_conf.get('password', None),
            )
    
    def __getitem__(self, key):
        return self.get(key)
    
    def __setitem__(self, key, val):
        return self.set(key, val)
    
    def get_path(self, key):
        if (not self._base) and (not key):
            raise KeyError('empty key is not allowed when no base defined')
        elif not self._base:
            path = key
        elif not key:
            path = self._base
        else:
            path = f'{self._base}.{key}'
        return path
    
    def get(self, key=None, default=Def):
        if not self.source:
            self.__class__.refresh()
        try:
            pval = self.source[self.get_path(key)]
        except KeyError:
            if default is Def:
                raise
            else:
                return default
                
        if isinstance(pval, bytes):
            try:
                val = dill.loads(pval)
            except dill.UnpicklingError:
                pass
        return val
        
    def set(self, key=None, val=Def):
        if not self.source:
            self.__class__.refresh()
        if val is Def:
            raise ValueError('value must be provided')
        if not isinstance(val, (int, str)):
            pval = dill.dumps(val)
        self.source[self.get_path(key)] = pval
    
class CacheDict(ProxyBase):
    __noproxy__ = ("_cache", "_path", "_default")
    
    def __init__(self, path=None, default={}):
        self._cache = None
        self._path = path
        self._default = default
        
    @property
    def __subject__(self):
        self.reload(force=False)
        return self._cache
    
    def reload(self, force=True):
        if self._cache is None or force:
            self._cache = Cache(self._path).get(default=self._default)
    
    def save(self):
        self.reload(force=False)
        Cache(self._path).set(val=self._cache)
        
class CacheQueue(ProxyBase):
    __noproxy__ = ("_cache", "_list", "_path")
    
    def __init__(self, path=None):
        self._cache = None
        self._list = None
        self._path = path
        
        
    @property
    def __subject__(self):
        self.reload(force=False)
        return self._cache
    
    def reload(self, force=True):
        if self._cache is None or force:
            self._cache = asyncio.Queue()
            self._list = []
            for item in self.load_hook(Cache(self._path).get(default=[])):
                self._cache.put_nowait(item)
                self._list.append(item)
                
    def load_hook(self, val):
        return val
        
    async def get(self):
        self.reload(force=False)
        item = await self._cache.get()
        self._list.remove(item)
        Cache(self._path).set(val=self.save_hook(self._list))
        return item
    
    async def put(self, item):
        self.reload(force=False)
        self._list.append(item)
        Cache(self._path).set(val=self.save_hook(self._list))
        return await self._cache.put(item)
    
    def save_hook(self, val):
        return val