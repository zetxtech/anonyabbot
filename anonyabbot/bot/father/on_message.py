import asyncio
import re
from pyrogram import Client
from pyrogram.types import Message as TM
from pyrogram.errors import RPCError

import anonyabbot

from ...utils import async_partial
from ...model import User, Group
from ..pool import start_group_bot
from .common import operation


class OnMessage:
    @operation(prohibited=None, conversation=True)
    async def on_messagge(
        self: "anonyabbot.FatherBot",
        client: Client,
        message: TM,
    ):
        info = async_partial(self.info, context=message, time=None)
        conv = self.conversation.get((message.chat.id, message.from_user.id), None)
        user: User = message.from_user.get_record()
        if not conv:
            message.continue_propagation()
        try:
            if message.text:
                if message.text.startswith("/"):
                    message.continue_propagation()
                if conv.status == "use_code":
                    used = user.use_code(message.text)
                    if used:
                        msg = "ℹ️ You have obtained the following roles:\n"
                        for u in used:
                            days = u.days if u.days else "permanent"
                            msg += f" {u.role.display} ({days})\n"
                    else:
                        msg = "⚠️ Invalid code."
                    return await info(msg)
                if conv.status == "ng_token":
                    match = re.search(r"[0-9]{8,10}:[a-zA-Z0-9_-]{35}", message.text)
                    if not match:
                        return await info("⚠️ Invalid token.")
                    token = match.group(0)
                    group = Group.get_or_none(token=token)
                    if group:
                        if group.disabled:
                            msg = (
                                "⚠️ The group is deleted.\n\n"
                                "if you want to recreate it, regenerate new bot token from [@botfather](t.me/botfather).\n"
                                "if you want to recover it, contact system admin.\n"
                            )
                            return await info(msg)
                        else:
                            return await info("⚠️ The bot is already a anonymous group.")
                    msg = await info("ℹ️ OK, please wait for startup ...")
                    try:
                        groupbot = await start_group_bot(token, creator=user)
                    except asyncio.TimeoutError:
                        await msg.delete()
                        return await info("⚠️ Timeout to start group bot, please retry later.")
                    except RPCError as e:
                        await msg.delete()
                        return await info(f"⚠️ Fail to start group bot:\n{e.MESSAGE.format(value=e.value)}.")
                    else:
                        await msg.delete()
                        return await info(
                            f"✅ Succeed. You can access your anonymous group [@{groupbot.group.username}](t.me/{groupbot.group.username}) now."
                        )
        finally:
            self.set_conversation(conv.context, None)

        message.continue_propagation()
