from typing import Union
from box import Box
from loguru import logger
from redisworks import Root

from .utils import ProxyBase
from .config import config

class Cache(ProxyBase):
    __noproxy__ = ("_cache",)
    
    def __init__(self):
        self._cache = None
    
    @property
    def __subject__(self):
        if not self._cache:
            self.refresh()
        return self._cache
    
    def get_redis(self):
        if not self._cache:
            self.refresh()
        if isinstance(self._cache, Root):
            return self._cache.red
        else:
            return None
    
    def refresh(self):
        redis = config.get('redis', None)
        if not redis:
            logger.warning('Redis is not configured, and caches will be lost during program restart.')
            self._cache = Box()
        else:
            self._cache = Root(
                host = redis.get('host', 'localhost'),
                port = int(redis.get('port', 6379)),
                db = int(redis.get('db', 0)),
                password = redis.get('password', None),
            )
            
    def __getitem__(self, arg):
        try:
            return self.__subject__[arg]
        except KeyError:
            self.__subject__[arg] = result = {}
            return result
        
cache: Union[Box, Root] = Cache()