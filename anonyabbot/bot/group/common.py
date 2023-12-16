import asyncio
from typing import Union

from loguru import logger
from pyrogram import ContinuePropagation, Client
from pyrogram.types import Message as TM, CallbackQuery as TC
from pyrogram.errors import UserDeactivated, MessageNotModified

import anonyabbot
from ...utils import nonblocking
from ...model import OperationError, MemberRole, Member, User


def operation(req: MemberRole = MemberRole.GUEST, conversation=False, allow_disabled=False, touch=True, concurrency='inf'):
    def deco(func):
        async def wrapper(*args, **kw):
            try:
                self: "anonyabbot.GroupBot"
                context: Union[TM, TC]
                client: Client
                if len(args) == 5:
                    self, handler, client, context, parameters = args  # from menu
                elif len(args) == 3:
                    self, client, context = args  # from message
                else:
                    raise ValueError("wrong number of arguments")
                try:
                    if touch:
                        await self.touch()
                    if not conversation:
                        self.set_conversation(context, status=None)
                    if (not allow_disabled) and self.group.disabled:
                        raise OperationError("this group has been deleted and cannot be operated")
                    if req:
                        member: Member = context.from_user.get_member(self.group)
                        if not member:
                            raise OperationError("you are not in this group")
                        member.validate(req, fail=True)
                        member.touch()
                    if not concurrency == 'inf':
                        user: User = context.from_user.get_record()
                        async with self.lock:
                            if not user in self.user_locks:
                                self.user_locks[user] = asyncio.Lock()
                        if concurrency == 'queue':
                            async with self.user_locks[user]:
                                return await func(*args, **kw)
                        elif concurrency == 'singleton':
                            async with nonblocking(self.user_locks[user]) as locked:
                                if locked:
                                    return await func(*args, **kw)
                        else:
                            raise ValueError(f'{concurrency} is not a valid concurrency')
                    else:
                        return await func(*args, **kw)
                except ContinuePropagation:
                    raise
                except OperationError as e:
                    try:
                        await self.info(f"⚠️ Fail: {e}.", context, alert=True)
                        if isinstance(context, TM):
                            await context.delete()
                    except:
                        pass
                except MessageNotModified:
                    pass
                except Exception as e:
                    if isinstance(e, ContinuePropagation):
                        raise
                    logger.opt(exception=e).warning("Callback error:")
                    try:
                        await self.info(f"⚠️ Error occured.", context, alert=True)
                    except:
                        pass
            except UserDeactivated as e:
                if self.group:
                    self.group.disabled = True
                    self.group.save()
                self.failed.set()
                logger.info(f"Group @{client.me.username} disabled because token deactivated.")

        return wrapper

    return deco
