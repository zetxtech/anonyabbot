import asyncio
from dataclasses import dataclass
from typing import Dict, Tuple, Union, Any, List
from datetime import datetime
import hashlib

from appdirs import user_data_dir
from pyrogram import Client, filters
from pyrogram.filters import Filter
from pyrogram.types import InputMedia, Message as TM, CallbackQuery as TC
from pyrogram.enums import ParseMode
from pyrubrum import (
    ParameterizedHandler,
    DictDatabase,
    RedisDatabase,
    Element,
    Menu,
    LinkMenu,
    PageMenu,
    ContentPageMenu,
    MenuStyle,
    PageStyle,
)

from .. import __name__ as __product__

from ..utils import to_iterable
from ..config import config
from ..cache import cache


@dataclass
class Conversation:
    context: Union[TM, TC]
    status: str
    data: Any


class Bot:
    name = None

    def __init__(self, token: str):
        self.token = token
        self.bot = Client(
            self.name,
            bot_token=token,
            api_id=config["tele.api_id"],
            api_hash=config["tele.api_hash"],
            proxy=config.get("proxy", None),
            workdir=config.get("basedir", user_data_dir(__product__)),
            workers=128,
        )
        self.jobs = []
        self.tasks = []

    async def start(self):
        self.tasks.extend([asyncio.create_task(j) for j in self.jobs])
        try:
            await self.bot.start()
            await self.setup()
            await asyncio.Event().wait()
        finally:
            for t in self.tasks:
                t.cancel()
            try:
                await self.bot.stop()
            except ConnectionError:
                pass

    async def setup(self):
        raise NotImplementedError()

    async def info(self, info: str, context: Union[TM, TC], reply: bool = False, time: int = 5, alert: bool = False):
        if isinstance(context, TM):
            if reply:
                msg = await context.reply(
                    info,
                    disable_notification=True,
                    disable_web_page_preview=True,
                )
            else:
                msg = await self.bot.send_message(
                    context.from_user.id,
                    info,
                    disable_notification=True,
                    disable_web_page_preview=True,
                )
            if time:
                await asyncio.sleep(time)
                await msg.delete()
            return msg
        elif isinstance(context, TC):
            await context.answer(info, show_alert=alert)
        else:
            raise TypeError("context should be message or callback query.")


class MenuBot(Bot):
    def __init__(self, *args, **kw) -> None:
        super().__init__(*args, **kw)
        self.conversion: Dict[Tuple[int, int], Conversation] = {}
        redis = cache.get_redis()
        if redis:
            db = RedisDatabase(redis)
        else:
            db = DictDatabase()
        self.menu = ParameterizedHandler(self.tree, db)

    def set_conversation(self, context: Union[TM, TC], status: str = None, data=None):
        if isinstance(context, TC):
            chatid = context.message.chat.id
            uid = context.from_user.id
        elif isinstance(context, TM):
            chatid = context.chat.id
            uid = context.from_user.id
        else:
            raise TypeError("context should be message or callback query.")
        self.conversion[(chatid, uid)] = Conversation(context, status, data) if status else None

    async def to_menu(self, menu_id: str, context: Union[TM, TC], **kw):
        if isinstance(context, TC):
            params = getattr(context, "parameters", {})
            params.update(**kw)
        elif isinstance(context, TM):
            params = kw
        else:
            raise TypeError("context should be message or callback query.")
        await self.menu[menu_id].on_update(self.menu, self.bot, context, params)

    async def to_menu_scratch(self, menu_id: str, chat: Union[str, int], user: Union[str, int], **kw):
        user = await self.bot.get_users(user)
        message = await self.bot.send_message(chat, "🔄 Loading")
        hash = hashlib.sha1(f"{message.chat.id}_{datetime.now().timestamp()}".encode())
        cid = str(int(hash.hexdigest(), 16) % (10**8))
        context = TC(
            client=self.bot,
            id=cid,
            from_user=user,
            message=message,
            chat_instance=None,
        )
        context.parameters = {}
        await self.to_menu(menu_id, context, **kw)
        return message

    def _prepare_params(
        self,
        id: str,
        button: str = None,
        display: Union[str, InputMedia] = None,
        filter: Filter = None,
        back=None,
        web=False,
        markdown=True,
        default=False,
        **kw,
    ):
        if button is None:
            func = getattr(self, f"button_{id.lstrip('_')}", None)
            if not func:
                button = "✅ OK"
            else:
                button = func
        if display is None:
            func = getattr(self, f"on_{id.lstrip('_')}", None)
            if not func:
                raise ValueError(f'menu content function "on_{id.lstrip("_")}" does not exist')
            else:
                display = func
        if filter is None:
            if id.startswith("_"):
                filter = ~filters.all
            else:
                filter = None
        menu_params = {
            "name": button,
            "menu_id": id,
            "content": display,
            "default": default,
            "message_filter": filter,
            "disable_web_page_preview": not web,
            "parse_mode": ParseMode.MARKDOWN if markdown else ParseMode.DISABLE,
        }
        style_params = {
            "back_text": "◀️ Back",
            "back_enable": False if back == False else True,
            "back_to": back,
        }
        return menu_params, style_params

    def _menu(
        self,
        id: str,
        button: str = None,
        display: Union[str, InputMedia] = None,
        filter: Filter = None,
        back=None,
        web=False,
        markdown=True,
        default=False,
    ):
        menu_params, style_params = self._prepare_params(
            id=id,
            button=button,
            display=display,
            filter=filter,
            back=back,
            web=web,
            markdown=markdown,
            default=default,
        )
        return Menu(**menu_params, style=MenuStyle(**style_params))

    def _keyboard(
        self,
        id: str,
        button: str = None,
        display: Union[str, InputMedia] = None,
        items: List[Union[Any, Element]] = None,
        filter: Filter = None,
        back=None,
        web=False,
        markdown=True,
        default=False,
        per_line=2,
        per_page=6,
        extras: List[str] = [],
        counter=False,
        page=False,
    ):
        if items is None:
            func = getattr(self, f"items_{id.lstrip('_')}", None)
            if not func:
                raise ValueError(f'menu items function "items_{id.lstrip("_")}" does not exist')
            else:
                items = func
        else:
            items = [i if isinstance(i, Element) else Element(str(i), str(i)) for i in items]
        menu_params, style_params = self._prepare_params(
            id=id,
            button=button,
            display=display,
            filter=filter,
            back=back,
            web=web,
            markdown=markdown,
            default=default,
        )
        style = PageStyle(
            **style_params,
            limit=per_line,
            limit_items=per_page,
            extras=to_iterable(extras),
            show_counter=counter,
            show_page=page,
            next_page_text="➡️",
            previous_page_text="⬅️",
        )
        return PageMenu(**menu_params, items=items, style=style)

    def _page(
        self,
        id: str,
        button: str = None,
        header: str = None,
        footer: str = None,
        filter: Filter = None,
        back=None,
        web=False,
        markdown=True,
        default=False,
        per_line=5,
        per_page=10,
        extras: List[str] = [],
        counter=False,
        page=False,
    ):
        menu_params, style_params = self._prepare_params(
            id=id,
            button=button,
            filter=filter,
            back=back,
            web=web,
            markdown=markdown,
            default=default,
        )
        if header is None:
            header = getattr(self, f"header_{id.lstrip('_')}", None)
        if footer is None:
            footer = getattr(self, f"footer_{id.lstrip('_')}", None)
        style = PageStyle(
            **style_params,
            limit=per_line,
            limit_items=per_page,
            extras=to_iterable(extras),
            show_counter=counter,
            show_page=page,
            next_page_text="➡️",
            previous_page_text="⬅️",
        )
        return ContentPageMenu(**menu_params, header=header, footer=footer, style=style)

    def _link(
        self,
        id: str,
        button: str = None,
        url: str = None,
    ):
        if button is None:
            button = "✅ OK"
        if url is None:
            func = getattr(self, f"url_{id.lstrip('_')}", None)
            if not func:
                raise ValueError(f'menu url function "url_{id.lstrip("_")}" does not exist')
            else:
                url = func
        return LinkMenu(name=button, menu_id=id, link=url)
