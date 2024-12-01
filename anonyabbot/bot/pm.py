from datetime import datetime, time
from pyrogram import filters, Client
from pyrogram.handlers import MessageHandler
from pyrogram.enums import ParseMode
from pyrogram.types import Message as TM, BotCommand
from loguru import logger
from peewee import DoesNotExist

from ..utils import parse_timedelta
from ..model import UserRole, User, DevPMBan, DevPMLog
from .base import Bot

logger = logger.bind(scheme="pm")


class PMBot(Bot):
    name = "pm"

    async def setup(self):
        await self.bot.set_bot_commands(
            [
                BotCommand("start", "PM developer"),
                BotCommand("delete", "Delete replied message"),
                BotCommand("ban", "(Admin) Ban [duration]"),
                BotCommand("unban", "(Admin) Unban"),
            ]
        )
        self.creator: User = next(User.all_in_role(UserRole.CREATOR))
        self.last_guest = None
        self.bot.add_handler(MessageHandler(self.on_start, filters.command("start")))
        self.bot.add_handler(MessageHandler(self.on_ban, filters.user(self.creator.uid) & filters.command("ban")))
        self.bot.add_handler(MessageHandler(self.on_unban, filters.user(self.creator.uid) & filters.command("unban")))
        self.bot.add_handler(
            MessageHandler(
                self.redirect_host, filters.user(self.creator.uid) & (~filters.service)
            )
        )
        self.bot.add_handler(MessageHandler(self.redirect_guest, ~filters.service))
        logger.info(f"Listening started: {self.bot.me.username}.")

    async def on_start(self, client: Client, message: TM):
        sender = message.from_user
        return await client.send_message(
            sender.id,
            "Hello, this is the developer of @anonyabbot. You can send feedback here and we will reply as soon as possible. Note that this is **not an anonymous chat group**. Please do not send irrelevant messages, or you may be **banned**.",
            parse_mode = ParseMode.MARKDOWN
        )

    async def on_ban(self, client: Client, message: TM):
        rm = message.reply_to_message
        if not rm:
            return await message.reply("⚠️ You need to reply to the target user's message.")
        log = DevPMLog.get_or_none(redirected_message=rm.id)
        if not log:
            return await message.reply("⚠️ You need to reply to the target user's message.")
        ur = log.user
        cmd = message.text.split(None, 1)
        try:
            _, duration = cmd
        except ValueError:
            duration = "365 d"
        try:
            td = parse_timedelta(duration)
        except AssertionError:
            return await message.reply("⚠️ Invalid duration, example: 2d 8h 10m")
        ban = DevPMBan.get_or_none(user=ur)
        if ban:
            ban.until += td
            ban.save()
        else:
            DevPMBan(user=ur, until=datetime.now() + td).save()
        return await message.reply("✅ Success")

    async def on_unban(self, client: Client, message: TM):
        rm = message.reply_to_message
        if not rm:
            return await message.reply("⚠️ You need to reply to the target user's message.")
        log = DevPMLog.get_or_none(redirected_message=rm.id)
        if not log:
            return await message.reply("⚠️ You need to reply to the target user's message.")
        ur = log.user
        ban = DevPMBan.get_or_none(user=ur)
        if not ban:
            return await message.reply("⚠️ User is not banned")
        ban.delete_instance()
        return await message.reply("✅ Success")

    async def redirect_host(self, client: Client, message: TM):
        rm = message.reply_to_message
        if not rm:
            if self.last_guest:
                await message.copy(self.last_guest)
            else:
                await message.reply("⚠️ You need to reply to the user's message.")
        else:
            log = DevPMLog.get_or_none(redirected_message=rm.id)
            if log:
                await message.copy(log.user.uid, reply_to_message_id=log.message)
            else:
                await message.reply("⚠️ You need to reply to the user's message.")

    async def redirect_guest(self, client: Client, message: TM):
        user: User = message.from_user.get_record()
        ban = DevPMBan.get_or_none(user=user)
        if ban:
            return await message.reply("⚠️ Sorry, the developer is currently busy.")
        else:
            self.last_guest = user.uid
            rmsg = await message.forward(self.creator.uid)
        today_0am = datetime.combine(datetime.today(), time(0, 0))
        try:
            DevPMLog.get(DevPMLog.user == user, DevPMLog.time > today_0am)
        except DoesNotExist:
            return await message.reply("✅ Message forwarded to developer. Please wait patiently for a reply, thank you.")
        else:
            return
        finally:
            DevPMLog(user=user, message=message.id, redirected_message=rmsg.id).save()
