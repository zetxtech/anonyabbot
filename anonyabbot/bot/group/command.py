import asyncio
from pyrogram import Client
from pyrogram.types import Message as TM
from pyrogram.errors import RPCError

import anonyabbot

from ...model import MemberRole, Member, OperationError, BanType, Message, PMBan, PMMessage, RedirectedMessage, User
from ...utils import async_partial
from .common import operation
from .worker import DeleteOperation, PinOperation, UnpinOperation
from .mask import MaskNotAvailable


class OnCommand:
    def get_member_reply_message(self: "anonyabbot.GroupBot", message: TM, allow_pm=False):
        member: Member = message.from_user.get_member(self.group)
        rm = message.reply_to_message
        if not rm:
            raise OperationError("no message replied")
        mr: Message = Message.get_or_none(mid=rm.id, member=member)
        if not mr:
            rmr = RedirectedMessage.get_or_none(mid=rm.id, to_member=member)
            if rmr:
                mr: Message = rmr.message
            else:
                if allow_pm:
                    pmm: PMMessage = PMMessage.get_or_none(redirected_mid=rm.id, to_member=member)
                    if pmm:
                        mr: PMMessage = pmm
                    else:
                        raise OperationError("this is not a anonymous message or is outdated")
                else:
                    raise OperationError("this is not a anonymous message or is outdated")
        return member, mr

    @operation(MemberRole.MEMBER)
    async def on_delete(self: "anonyabbot.GroupBot", client: Client, message: TM):
        await message.delete()
        info = async_partial(self.info, context=message)
        member, mr = self.get_member_reply_message(message)
        member.check_ban(BanType.MESSAGE)
        if not mr.member.id == member.id:
            if not member.role >= MemberRole.ADMIN_BAN:
                return await info(f"⚠️ Only messages sent by you can be deleted.")
        e = asyncio.Event()
        op = DeleteOperation(member=member, finished=e, message=mr)
        await self.queue.put(op)
        msg: TM = await info(f"🔃 Message revoking from all users...", time=None)
        try:
            await asyncio.wait_for(e.wait(), 120)
        except asyncio.TimeoutError:
            await msg.edit("⚠️ Timeout to revoke this message.")
        else:
            await msg.edit(f"🗑️ Message deleted ({op.requests-op.errors}/{op.requests}).")
        await asyncio.sleep(2)
        await msg.delete()

    @operation(MemberRole.MEMBER)
    async def on_change(self: "anonyabbot.GroupBot", client: Client, message: TM):
        await message.delete()
        info = async_partial(self.info, context=message)
        member: Member = message.from_user.get_member(self.group)
        _, mask = await self.unique_mask_pool.get_mask(member, renew=True)
        await info(f"🌈 Your mask has been changed to: {mask}")

    @operation(MemberRole.MEMBER)
    async def on_setmask(self: "anonyabbot.GroupBot", client: Client, message: TM):
        await message.delete()
        info = async_partial(self.info, context=message)
        user: User = message.from_user.get_record()
        if not user.is_prime:
            await info(f"⚠️ This function is only available to [prime](t.me/{self.bot.me.username}?start=_createcode) users.")
            return
        msg: TM = await info("⬇️ Please enter an emoji as your mask:", time=None)
        self.set_conversation(message, "sm_mask", data=msg)
        await asyncio.sleep(120)
        if await msg.delete():
            self.set_conversation(message, None)
            await info("⚠️ Timeout.", time=2)

    @operation()
    async def on_ban(self: "anonyabbot.GroupBot", client: Client, message: TM):
        await message.delete()
        info = async_partial(self.info, context=message)

        cmd = message.text.split(None, 1)
        try:
            _, uid = cmd
        except ValueError:
            member, mr = self.get_member_reply_message(message, allow_pm=True)
            if isinstance(mr, Message):
                target = mr.member
            elif isinstance(mr, PMMessage):
                target = mr.from_member
                pmban = PMBan.get_or_none(from_member=target, to_member=member)
                if not pmban:
                    PMBan.create(from_member=target, to_member=member)
                return await info("✅ This member will not send private messages to you any more.")
        else:
            user = await self.bot.get_users(uid)
            target = user.get_member(self.group)
            if not target:
                raise OperationError("member not found in this group")
            member: Member = message.from_user.get_member(self.group)
        member.validate(MemberRole.ADMIN_BAN)
        if target.role >= MemberRole.ADMIN:
            member.validate(MemberRole.ADMIN_ADMIN, fail=True)
        if target.role >= MemberRole.ADMIN_ADMIN:
            member.validate(MemberRole.CREATOR, fail=True)
        if target.id == member.id:
            return await info("⚠️ Can not ban yourself.")
        if target.role >= member.role:
            return await info("⚠️ Permission denied.")
        if target.role == MemberRole.BANNED:
            return await info("⚠️ The user is already banned.")

        target.role = MemberRole.BANNED
        target.save()
        return await info("🚫 Member banned.")

    @operation()
    async def on_unban(self: "anonyabbot.GroupBot", client: Client, message: TM):
        await message.delete()
        info = async_partial(self.info, context=message)

        cmd = message.text.split(None, 1)
        try:
            _, uid = cmd
        except ValueError:
            member, mr = self.get_member_reply_message(message, allow_pm=True)
            if isinstance(mr, Message):
                target = mr.member
            elif isinstance(mr, PMMessage):
                target = mr.from_member
                pmban = PMBan.get_or_none(from_member=target, to_member=member)
                if pmban:
                    pmban.delete_instance()
                return await info("✅ This member is now able to send private messages.")
        else:
            user = await self.bot.get_users(uid)
            target = user.get_member(self.group)
            if not target:
                raise OperationError("member not found in this group")
            member: Member = message.from_user.get_member(self.group)
        member.validate(MemberRole.ADMIN_BAN)
        if target.role >= MemberRole.ADMIN:
            member.validate(MemberRole.ADMIN_ADMIN, fail=True)
        if target.role >= MemberRole.ADMIN_ADMIN:
            member.validate(MemberRole.CREATOR, fail=True)
        if target.id == member.id:
            return await info("⚠️ Can not unban yourself.")
        if target.role >= member.role:
            return await info("⚠️ Permission denied.")
        if not target.role == MemberRole.BANNED:
            return await info("⚠️ The user is not banned.")

        target.role = MemberRole.GUEST
        target.save()
        return await info("✅ Member unbanned.")

    @operation(MemberRole.ADMIN_MSG)
    async def on_pin(self: "anonyabbot.GroupBot", client: Client, message: TM):
        await message.delete()
        info = async_partial(self.info, context=message)
        user: User = message.from_user.get_record()
        if (not self.group.is_prime) and (not user.is_prime):
            await info(f"⚠️ This function is only available to groups created by [prime](t.me/{self.bot.me.username}?start=_createcode) users.")
            return
        member, mr = self.get_member_reply_message(message)
        mr.pinned = True
        mr.save()
        e = asyncio.Event()
        op = PinOperation(member=member, finished=e, message=mr)
        await self.queue.put(op)
        msg: TM = await info(f"🔃 Pinning message for all users...", time=None)
        try:
            await asyncio.wait_for(e.wait(), 120)
        except asyncio.TimeoutError:
            await msg.edit("⚠️ Timeout to pin this message.")
        else:
            await msg.edit(f"📌 Message pinned ({op.requests-op.errors}/{op.requests}).")
        await asyncio.sleep(2)
        await msg.delete()

    @operation(MemberRole.ADMIN_MSG)
    async def on_unpin(self: "anonyabbot.GroupBot", client: Client, message: TM):
        await message.delete()
        info = async_partial(self.info, context=message)
        user: User = message.from_user.get_record()
        if (not self.group.is_prime) and (not user.is_prime):
            await info(f"⚠️ This function is only available to groups created by [prime](t.me/{self.bot.me.username}?start=_createcode) users.")
            return
        member, mr = self.get_member_reply_message(message)
        mr.pinned = False
        mr.save()
        e = asyncio.Event()
        op = UnpinOperation(member=member, finished=e, message=mr)
        await self.queue.put(op)
        msg: TM = await info(f"🔃 Unpinning message for all users...", time=None)
        try:
            await asyncio.wait_for(e.wait(), 120)
        except asyncio.TimeoutError:
            await msg.edit("⚠️ Timeout to unpin this message.")
        else:
            await msg.edit(f"📌 Message unpinned ({op.requests-op.errors}/{op.requests}).")
        await asyncio.sleep(2)
        await msg.delete()

    @operation(MemberRole.ADMIN_BAN)
    async def on_reveal(self: "anonyabbot.GroupBot", client: Client, message: TM):
        await message.delete()
        info = async_partial(self.info, context=message)
        _, mr = self.get_member_reply_message(message)
        target: Member = mr.member
        msg = (
            f"ℹ️ Profile of this member:\n\n"
            f"Name: {target.user.name}\n"
            f"ID: {target.user.uid}\n"
            f"Role in group: {target.role.display.title()}\n"
            f"Joining date: {target.created.strftime('%Y-%m-%d')}\n"
            f"Message count: {target.n_messages}\n"
            f"Last Activity: {target.last_activity.strftime('%Y-%m-%d')}\n"
            f"Last Mask: {target.last_mask}\n\n"
            f"👁️‍🗨️ This panel is only visible to you."
        )
        await info(msg, time=15)

    @operation(MemberRole.ADMIN_BAN)
    async def on_manage(self: "anonyabbot.GroupBot", client: Client, message: TM):
        await message.delete()
        _, mr = self.get_member_reply_message(message)
        target: Member = mr.member
        return await self.to_menu_scratch("_member_detail", message.chat.id, message.from_user.id, member_id=target.id)

    async def pm(self, message: TM):
        info = async_partial(self.info, context=message)

        content = message.text or message.caption
        
        try:
            member, mr = self.get_member_reply_message(message, allow_pm=True)
            if isinstance(mr, Message):
                target: Member = mr.member
            elif isinstance(mr, PMMessage):
                target: Member = mr.from_member
            member.check_ban(BanType.PM_USER)
            if target.role >= MemberRole.ADMIN:
                member.check_ban(BanType.PM_ADMIN)
            if target.role <= MemberRole.LEFT:
                raise OperationError('this user is not in this group anymore')
            if target.check_ban(BanType.RECEIVE, check_group=False, fail=False):
                raise OperationError('this user is banned from receiving messages')
            pmban = PMBan.get_or_none(from_member=member, to_member=target)
            if pmban:
                raise OperationError('this user is not willing to receive private messages from you')
            self.check_message(message, member)
        except OperationError as e:
            await info(f"⚠️ Sorry, {e}, and this message will be deleted soon.", time=30)
            await message.delete()
            return
        
        if member.pinned_mask:
            mask = member.pinned_mask
            created = False
        else:
            try:
                created, mask = await self.unique_mask_pool.get_mask(member)
            except MaskNotAvailable:
                await info(f"⚠️ Sorry, no mask is currently available, please set mask manually and try again. This message will be deleted soon.", time=30)
                await message.delete()
                return
        
        content = f'{mask} (👁️ PM) | {content}'
        
        if created:
            msg: TM = await info(f"🔃 PM message sending as {mask} ...", time=None)
        else:
            msg: TM = await info("🔃 PM message sending ...", time=None)
        
        try:
            if message.text:
                message.text = content
                masked_message = await message.copy(target.user.uid)
            else:
                masked_message = await message.copy(target.user.uid, caption=content)
        except RPCError as e:
            await msg.edit('⚠️ Fail to send, and this message will be deleted soon.')
            await asyncio.sleep(30)
            await msg.delete()
            return
        else:
            PMMessage.create(from_member=member, to_member=target, mid=message.id, redirected_mid=masked_message.id)
            await msg.edit('✅ PM message sent.')
            await asyncio.sleep(5)
            await msg.delete()


    @operation(MemberRole.MEMBER)
    async def on_pm(self: "anonyabbot.GroupBot", client: Client, message: TM):
        info = async_partial(self.info, context=message)
        
        if not self.group.is_prime:
            await info(f"⚠️ This function is only available to groups created by [prime](t.me/{self.bot.me.username}?start=_createcode) users.")
            return
        
        content = message.text or message.caption
        
        cmd = content.split(None, 1)
        try:
            _, content = cmd
        except ValueError:
            await message.delete()
            return await info('⚠️ Use "/pm [text]" to send private messages.')
        
        message.text = content

        await self.pm(message)