import asyncio
import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from pyrogram.types import Message as TM
from pyrogram.errors import RPCError, UserIsBlocked, UserDeactivated

import anonyabbot

from ...cache import CacheQueue
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

@dataclass(kw_only=True)
class BulkRedirectOperation(Operation):
    messages: List[Message]
    
@dataclass(kw_only=True)
class BulkPinOperation(Operation):
    messages: List[Message]

class WorkerQueue(CacheQueue):
    __noproxy__ = ("_bot",)
    
    def __init__(self, path=None, bot=None):
        super().__init__(path)
        self._bot = bot
    
    def save_hook(self, val):
        results = []
        for i in val:
            ci = copy.copy(i)
            ci.finished = None
            results.append(ci)
        return results
    
    def load_hook(self, val):
        for i in val:
            if i.finished is None:
                i.finished = asyncio.Event()
            ic = getattr(i, 'context', None)
            if ic:
                if not hasattr(ic, '_client'):
                    setattr(ic, '_client', self._bot)
        return val

class Worker:
    async def report_status(self: "anonyabbot.GroupBot", time: int, requests: int, errors: int):
        self.worker_status['time'] += time
        self.worker_status['requests'] += requests
        self.worker_status['errors'] += errors
        self.worker_status.save()
        async with pool.worker_status_lock:
            pool.worker_status['time'] += time
            pool.worker_status['requests'] += requests
            pool.worker_status['errors'] += errors
            pool.worker_status.save()
    
    async def bulk_redirector(self: "anonyabbot.GroupBot", op: BulkRedirectOperation):
        try:
            if op.member.check_ban(BanType.RECEIVE, check_group=False, fail=False):
                return
            if op.member.is_banned:
                return
            for message in op.messages:
                await asyncio.sleep(1)
                if message.member.id == op.member.id:
                    continue
                
                context = await self.bot.get_messages(message.member.user.uid, message.mid)
                
                content = context.text or context.caption
                if content:
                    content = f"{message.mask} | {content}"
                else:
                    content = f"{message.mask} has sent a media."
                
                rmr = None
                if message.reply_to:
                    rmr = message.reply_to.get_redirect_for(op.member)

                try:
                    if context.text:
                        context.text = content
                        masked_message = await context.copy(
                            op.member.user.uid,
                            reply_to_message_id=rmr.mid if rmr else None,
                        )
                    else:
                        masked_message = await context.copy(
                            op.member.user.uid,
                            caption=content,
                            reply_to_message_id=rmr.mid if rmr else None,
                        )
                    if not masked_message:
                        op.errors += 1
                        continue
                except RPCError as e:
                    if isinstance(e, (UserIsBlocked, UserDeactivated)) and not op.member.role == MemberRole.CREATOR:
                        op.member.role = MemberRole.LEFT
                        op.member.save()
                    op.errors += 1
                else:
                    RedirectedMessage(mid=masked_message.id, message=message, to_member=op.member).save()
                finally:
                    op.requests += 1
            waiting_time = (datetime.now() - op.created).total_seconds() 
            await self.report_status(waiting_time, op.requests, op.errors)
        except Exception as e:
            self.log.opt(exception=e).warning("Bulk redirector error:")
        finally:
            op.finished.set()
            
    async def bulk_pinner(self: "anonyabbot.GroupBot", op: BulkPinOperation):
        try:
            if op.member.check_ban(BanType.RECEIVE, check_group=False, fail=False):
                return
            if op.member.is_banned:
                return
            for message in op.messages:
                try:
                    if op.member.id == message.member.id:
                        await self.bot.pin_chat_message(
                            op.member.user.uid, message.mid, both_sides=True, disable_notification=True
                        )
                    else:
                        masked_message = message.get_redirect_for(op.member)
                        if masked_message:
                            await self.bot.pin_chat_message(
                                op.member.user.uid, masked_message.mid, both_sides=True, disable_notification=True
                            )
                except RPCError as e:
                    if isinstance(e, (UserIsBlocked, UserDeactivated)) and not op.member.role == MemberRole.CREATOR:
                        op.member.role = MemberRole.LEFT
                        op.member.save()
                    op.errors += 1
                finally:
                    op.requests += 1
        except Exception as e:
            self.log.opt(exception=e).warning("Bulk pinner error:")
        finally:
            op.finished.set()
    
    async def worker(self: "anonyabbot.GroupBot"):
        while True:
            op = await self.queue.get()
            if isinstance(op, BulkRedirectOperation):
                asyncio.create_task(self.bulk_redirector(op))
                continue
            if isinstance(op, BulkPinOperation):
                asyncio.create_task(self.bulk_pinner(op))
                continue
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
                        if op.message.reply_to:
                            rmr = op.message.reply_to.get_redirect_for(m)

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
                            if not masked_message:
                                op.errors += 1
                                continue
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