import asyncio
import functools
from pathlib import Path
from threading import Thread, Event
import time
from typing import Union

from box import BoxError, ConfigBox
from loguru import logger
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from .utils import ProxyBase

DEFAULT_CONF = {}    

class ConfigError(BoxError):
    pass

class ConfigChangeHandler(FileSystemEventHandler):
    def __init__(self, *args, func=None, **kw):
        super().__init__(*args, **kw)
        self.func = func
    
    def on_modified(self, event: FileSystemEvent):
        logger.info(f'Config file has changed, reloading.')
        self.func()

class Config(ProxyBase):
    __noproxy__ = ("_conf_file", "_cache", "_observer", "__getitem__")

    def __init__(self, conf_file=None):
        self._conf_file = conf_file
        self._cache = None
        self._observer = None

    @property
    def __subject__(self):
        if not self._cache:
            self.reload_conf(conf_file=self._conf_file)
        return self._cache

    def reset(self):
        self._cache = None

    def start_observer(self, conf_file, box):
        if self._observer:
            self._observer.stop()
        self._observer = obs = Observer()
        func = functools.partial(self.reload_conf, box = box)
        obs.schedule(ConfigChangeHandler(func=func), conf_file)
        obs.start()
        
    def reload_conf(self, conf_file=None, box=None):
        """Load config from provided file or config.toml at cwd."""
        if not box:
            box = ConfigBox(DEFAULT_CONF, box_dots=True)
        default_conf = Path("./config.toml")
        if conf_file:
            conf_file = Path(conf_file)
        elif self._conf_file:
            conf_file = Path(self._conf_file)
        elif default_conf.is_file():
            conf_file = default_conf
        else:
            logger.debug(f"No config found from provided file or ./{default_conf}.")
        if conf_file:
            if conf_file.suffix.lower() == ".toml":
                box.merge_update(ConfigBox.from_toml(filename=conf_file))
            elif conf_file.suffix.lower() in (".yaml", ".yml"):
                box.merge_update(ConfigBox.from_yaml(filename=conf_file))
            else:
                logger.warning(f'Can not load config file "{conf_file}", a yaml/toml file is required.')
        logger.debug(f'Now using config file at "{conf_file.absolute()}".')
        self._conf_file = conf_file
        self._cache = box
        self.start_observer(conf_file, box)

    def __getitem__(self, key):
        try:
            return self.__subject__[key]
        except BoxError:
            msg = f'can not find config key "{key}", please check your config file or env var.'
            raise ConfigError(msg) from None

config: Union[ConfigBox, Config] = Config()
