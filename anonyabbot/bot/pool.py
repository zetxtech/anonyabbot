import asyncio
from datetime import datetime

from loguru import logger

from ..utils import AsyncTaskPool
from ..cache import CacheDict
from ..model import Group, User
from .group import GroupBot

pool = AsyncTaskPool()

token_tasks = {}
token_start_event = {}
token_cls = {}

start_queue = asyncio.Queue()

start_time = datetime.now()

worker_status = CacheDict(
    'system.statistics.worker.status',
    default={
        'time': 0,
        'requests': 0,
        'errors': 0
    }
)
worker_status_lock = asyncio.Lock()

async def queue_monitor():
    while True:
        token, creator, event = await start_queue.get()
        token_cls[token] = gb = GroupBot(token, creator, event)
        token_tasks[token] = pool.add(gb.start())


async def stop_group_bot(token: str):
    task: asyncio.Task = token_tasks.get(token, None)
    if task:
        token_tasks.pop(token, None)
        token_start_event.pop(token, None)
        token_cls.pop(token, None)
        task.cancel()


async def start_group_bot(token: str, creator: User):
    task: asyncio.Task = token_tasks.get(token, None)
    if task and not task.done():
        return token_cls[token]
    event = asyncio.Event()
    token_start_event[token] = event
    await start_queue.put((token, creator, event))
    await asyncio.wait_for(event.wait(), 120)
    cls = token_cls[token]
    if cls.boot_exception:
        await stop_group_bot(token)
        raise cls.boot_exception
    else:
        return cls


async def start_groups():
    events = []
    g: Group
    for g in Group.select().where(~(Group.disabled)):
        e = asyncio.Event()
        events.append(e)
        await start_queue.put((g.token, g.creator, e))
    for e in events:
        await e.wait()
    logger.info("All groupbots are started.")


async def start():
    pool.add(queue_monitor())
    pool.add(start_groups())
    await pool.wait()
