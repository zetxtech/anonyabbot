import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from pyrogram.types import Message as TM
from pyrogram.errors import RPCError, UserIsBlocked, UserDeactivated

import anonyabbot

from ...model import MemberRole, Message, Member, BanType, RedirectedMessage
from .. import pool

@dataclass(kw_only=True)
class Operation:
    member: Member
    finished: asyncio.Event = field(default_factory=asyncio.Event)
    requests: int = 0
    errors: int = 0
    created: datetime = field(default_factory=datetime.now)


@dataclass(kw_only=True)
class BroadcastOperation(Operation):
    context: TM
    message: Message
    reply_to: Message = None


@dataclass(kw_only=True)
class EditOperation(Operation):
    context: TM
    message: Message


@dataclass(kw_only=True)
class DeleteOperation(Operation):
    message: Message


@dataclass(kw_only=True)
class PinOperation(Operation):
    message: Message


@dataclass(kw_only=True)
class UnpinOperation(Operation):
    message: Message


class Worker:
    async def report_status(self: "anonyabbot.GroupBot", time: int, requests: int, errors: int):
        self.worker_status['time'] += time
        self.worker_status['requests'] += requests
        self.worker_status['errors'] += errors
        async with pool.worker_status_lock:
            pool.worker_status['time'] += time
            pool.worker_status['requests'] += requests
            pool.worker_status['errors'] += errors
    
    async def worker(self: "anonyabbot.GroupBot"):
        while True:
            op = await self.queue.get()
            try:
                if not op:
                    break
                if isinstance(op, BroadcastOperation):
                    if self.group.cannot(BanType.RECEIVE):
                        op.finished.set()
                        continue

                    content = op.context.text or op.context.caption

                    if content:
                        content = f"{op.message.mask} | {content}"
                    else:
                        content = f"{op.message.mask} has sent a media."

                    m: Member
                    for m in self.group.user_members():
                        if m.id == op.member.id:
                            continue
                        if m.is_banned:
                            continue
                        if m.check_ban(BanType.RECEIVE, check_group=False, fail=False):
                            continue

                        rmr = None
                        if op.reply_to:
                            rmr = op.reply_to.get_redirect_for(m)

                        try:
                            if op.context.text:
                                op.context.text = content
                                masked_message = await op.context.copy(
                                    m.user.uid,
                                    reply_to_message_id=rmr.mid if rmr else None,
                                )
                            else:
                                masked_message = await op.context.copy(
                                    m.user.uid,
                                    caption=content,
                                    reply_to_message_id=rmr.mid if rmr else None,
                                )
                        except RPCError as e:
                            if isinstance(e, (UserIsBlocked, UserDeactivated)) and not m.role == MemberRole.CREATOR:
                                m.role = MemberRole.LEFT
                                m.save()
                            op.errors += 1
                        else:
                            RedirectedMessage(mid=masked_message.id, message=op.message, to_member=m).save()
                        finally:
                            op.requests += 1

                elif isinstance(op, EditOperation):
                    if self.group.cannot(BanType.RECEIVE):
                        op.finished.set()
                        continue

                    content = op.context.text or op.context.caption

                    if content:
                        content = f"{op.message.mask} | {content}"
                    else:
                        content = f"{op.message.mask} has sent a media."

                    m: Member
                    for m in self.group.user_members():
                        if m.id == op.member.id:
                            continue
                        if m.is_banned:
                            continue
                        if m.check_ban(BanType.RECEIVE, check_group=False, fail=False):
                            continue

                        try:
                            masked_message = op.message.get_redirect_for(m)
                            if masked_message:
                                await self.bot.edit_message_text(masked_message.to_member.user.uid, masked_message.mid, content)
                        except RPCError as e:
                            if isinstance(e, (UserIsBlocked, UserDeactivated)) and not m.role == MemberRole.CREATOR:
                                m.role = MemberRole.LEFT
                                m.save()
                            op.errors += 1
                        finally:
                            op.requests += 1

                elif isinstance(op, DeleteOperation):
                    if self.group.cannot(BanType.RECEIVE):
                        op.finished.set()
                        continue

                    m: Member
                    for m in self.group.user_members():
                        if m.is_banned:
                            continue
                        if m.check_ban(BanType.RECEIVE, check_group=False, fail=False):
                            continue

                        try:
                            if m.id == op.message.member.id:
                                await self.bot.delete_messages(op.message.member.user.uid, op.message.mid)
                            else:
                                masked_message = op.message.get_redirect_for(m)
                                if masked_message:
                                    await self.bot.delete_messages(masked_message.to_member.user.uid, masked_message.mid)
                        except RPCError as e:
                            if isinstance(e, (UserIsBlocked, UserDeactivated)) and not m.role == MemberRole.CREATOR:
                                m.role = MemberRole.LEFT
                                m.save()
                            op.errors += 1
                        finally:
                            op.requests += 1

                elif isinstance(op, PinOperation):
                    if self.group.cannot(BanType.RECEIVE):
                        op.finished.set()
                        continue

                    m: Member
                    for m in self.group.user_members():
                        if m.is_banned:
                            continue
                        
                        try:
                            if m.id == op.message.member.id:
                                await self.bot.pin_chat_message(
                                    op.message.member.user.uid, op.message.mid, both_sides=True, disable_notification=True
                                )
                            else:
                                masked_message = op.message.get_redirect_for(m)
                                if masked_message:
                                    await self.bot.pin_chat_message(
                                        masked_message.to_member.user.uid, masked_message.mid, both_sides=True, disable_notification=True
                                    )
                        except RPCError as e:
                            if isinstance(e, (UserIsBlocked, UserDeactivated)) and not m.role == MemberRole.CREATOR:
                                m.role = MemberRole.LEFT
                                m.save()
                            op.errors += 1
                        finally:
                            op.requests += 1

                elif isinstance(op, UnpinOperation):
                    if self.group.cannot(BanType.RECEIVE):
                        op.finished.set()
                        continue

                    m: Member
                    for m in self.group.user_members():
                        if m.is_banned:
                            continue

                        try:
                            if m.id == op.message.member.id:
                                await self.bot.unpin_chat_message(op.message.member.user.uid, op.message.mid)
                            else:
                                masked_message = op.message.get_redirect_for(m)
                                if masked_message:
                                    await self.bot.unpin_chat_message(masked_message.to_member.user.uid, masked_message.mid)
                        except RPCError as e:
                            if isinstance(e, (UserIsBlocked, UserDeactivated)) and not m.role == MemberRole.CREATOR:
                                m.role = MemberRole.LEFT
                                m.save()
                            op.errors += 1
                        finally:
                            op.requests += 1

                
                waiting_time = (datetime.now() - op.created).total_seconds() 
                await self.report_status(waiting_time, op.requests, op.errors)
            except Exception as e:
                self.log.opt(exception=e).warning("Worker error:")
            finally:
                op.finished.set()