import asyncio
from pyrogram import Client
from pyrogram.types import Message as TM, CallbackQuery as TC, InlineKeyboardButton, InlineKeyboardMarkup

import anonyabbot

from ...model import Member, User, MemberRole
from ...utils import async_partial
from .worker import BulkRedirectOperation, BulkPinOperation
from .common import operation


class Start:
    async def send_welcome_msg(self: "anonyabbot.GroupBot", user: User, msg: str = None, button_spec: str = None, photo: str = None):
        if msg:
            msg = msg.format(
                first_name=user.firstname,
                last_name=user.lastname,
                masked_name=user.masked_name,
                name=user.name,
                markdown=user.markdown,
            )
        else:
            msg = (
                "🌈 Welcome to this fully anonymous group.\n\n"
                "All messages send to the bot will be redirected to all members with your identity hidden.\n"
                "You will use an emoji as your mask during chatting.\n"
                "Only admins can reveal your identity.\n"
                "Have fun!"
            )
        
        if not 'anonyabbot' in msg:
            msg += '\n\n © Powered by @anonyabbot.'

        if button_spec:
            keyboard = []
            for l in button_spec.splitlines():
                line = []
                for b in l.split("|"):
                    display, url = b.split(":", 1)
                    display = display.strip()
                    url = url.strip()
                    button = InlineKeyboardButton(display, url=url)
                    line.append(button)
                keyboard.append(line)
            markup = InlineKeyboardMarkup(keyboard)
        else:
            markup = None

        if photo:
            return await self.bot.send_photo(user.uid, photo, caption=msg, reply_markup=markup)
        else:
            return await self.bot.send_message(user.uid, msg, reply_markup=markup)
        
    async def send_latest_messages(self: "anonyabbot.GroupBot", member: Member, context: TM):
        if self.group.welcome_latest_messages:
            nrpm = member.not_redirected_pinned_messages()
            if len(nrpm) > 0:
                e = asyncio.Event()
                op = BulkRedirectOperation(messages=reversed(nrpm), member=member, finished=e)
                info = async_partial(self.info, context=context)
                msg: TM = await info(f"🔃 Loading pinned messages ...", time=None)
                await self.queue.put(op)
                try:
                    await asyncio.wait_for(e.wait(), 120)
                except asyncio.TimeoutError:
                    await msg.edit("⚠️ Timeout to load pinned messages.")
                    await asyncio.sleep(3)
                await msg.delete()
            
                e = asyncio.Event()
                op = BulkPinOperation(messages=reversed(list(member.pinned_messages())), member=member, finished=e)
                info = async_partial(self.info, context=context)
                msg: TM = await info(f"🔃 Pinning messages ...", time=None)
                await self.queue.put(op)
                try:
                    await asyncio.wait_for(e.wait(), 120)
                except asyncio.TimeoutError:
                    await msg.edit("⚠️ Timeout to pin messages.")
                    await asyncio.sleep(3)
                await msg.delete()
                
            nrm = member.not_redirected_messages()
            if len(nrm) > 0:
                e = asyncio.Event()
                op = BulkRedirectOperation(messages=reversed(nrm), member=member, finished=e)
                info = async_partial(self.info, context=context)
                msg: TM = await info(f"🔃 Loading latest messages ...", time=None)
                await self.queue.put(op)
                try:
                    await asyncio.wait_for(e.wait(), 120)
                except asyncio.TimeoutError:
                    await msg.edit("⚠️ Timeout to load latest messages.")
                    await asyncio.sleep(3)
                await msg.delete()
            

    @operation(req=None)
    async def on_start(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TM,
        parameters: dict,
    ):
        async def welcome(self, user, member, context):
            await self.send_welcome_msg(
                user=user,
                msg=self.group.welcome_message,
                button_spec=self.group.welcome_message_buttons,
                photo=self.group.welcome_message_photo,
            )
            await self.send_latest_messages(
                member=member,
                context=context,
            )
          
        member: Member = context.from_user.get_member(self.group)
        user: User = context.from_user.get_record()
        if member:
            if isinstance(context, TM):
                await context.delete()
            mask = member.pinned_mask or await self.unique_mask_pool.mask_for(member)
            if member.role == MemberRole.LEFT:
                member.role = MemberRole.GUEST
                member.save()
                await welcome(self, user, member, context)
            else:
                return (
                    "ℹ️ Powered by @anonyabbot.\n"
                    "🌈 Group status:\n\n"
                    f" Members: {self.group.n_members}\n"
                    f" Non-Guests: {self.group.s_all_has_role(MemberRole.MEMBER).count()}\n\n"
                    "👤 Your membership:\n\n"
                    f" Role: {member.role.display.title()}\n"
                    f' Mask: {mask if mask else "<Not Active>"}\n\n'
                    f"👁️‍🗨️ This panel is only visible to you."
                )
        else:
            member = Member.create(group=self.group, user=user, role=MemberRole.GUEST)
            await welcome(self, user, member, context)

    @operation()
    async def on_leave_group_confirm(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        member: Member = context.from_user.get_member(self.group)
        if member.role == MemberRole.CREATOR:
            await context.answer("⚠️ Creator of the group can not leave.")
            await self.to_menu("start", context)
            return
        return f"⚠️ Are you sure to leave the group?\n⚠️ Your current role is: {member.role.display}."

    @operation()
    async def on_leave_group(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        member: Member = context.from_user.get_member(self.group)
        member.role = MemberRole.LEFT
        member.save()
        await context.answer("✅ You have left the group and will no longer receive messages.", show_alert=True)
        await asyncio.sleep(2)
        await context.message.delete()
        return

    @operation(MemberRole.ADMIN)
    async def on_manage_group(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        await self.to_menu("_group_details", context)

    @operation(req=None)
    async def on_close_start(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        await context.message.delete()
        await context.answer("✅ Closed.")
