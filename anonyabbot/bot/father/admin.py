from datetime import datetime, timedelta
from textwrap import indent
from pyrogram import Client
from pyrogram.types import CallbackQuery as TC
from pyrubrum import Element
from peewee import fn

import anonyabbot

from ...utils import to_iterable, truncate_str
from ...model import User, UserRole, Group, Member, Message
from ..pool import start_time, worker_status, stop_group_bot
from .common import operation


class Admin:
    @operation(UserRole.ADMIN)
    async def on_admin(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        n_groups = Group.select().where(~(Group.disabled)).count()
        date_ago = datetime.now() - timedelta(days=7)
        n_active_groups = Group.select().where(~(Group.disabled), Group.last_activity >= date_ago).count()
        latest_user: User = User.select().order_by(User.created.desc()).get()
        running_time = ":".join(str(datetime.now() - start_time).split(":")[:3]).split('.')[0]
        waiting_delay = f"{worker_status['time'] / worker_status['requests']:.1f}" if worker_status['requests'] else "inf"
        msg = f"ℹ️ System info:\n\n"
        fields = [
            f"Users: {User.select().count()}",
            f"Groupers: {User.n_in_role(UserRole.GROUPER)}",
            f"Awarded Users: {User.n_in_role(UserRole.AWARDED)}",
            f"Paying Users: {User.n_in_role(UserRole.PAYING)}",
            f"Admins: {User.n_in_role(UserRole.ADMIN)}",
            f"Latest User: {latest_user.markdown}",
            f"Groups: {n_groups}",
            f"Active Groups: {n_active_groups}",
            f"Running Time: {running_time}",
            f"Average Delay: {waiting_delay} seconds",
            f"Messages: {Message.select().count()}",
        ]
        msg += indent("\n".join(fields), "  ")
        return msg

    @operation(UserRole.ADMIN)
    async def items_generate_codes_select_role(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        current_selection = parameters.get("gcsr_current", [])
        items = []
        for r in UserRole:
            button = r.name
            if r.value in current_selection:
                button = f"✓ {button}"
            items.append(Element(button, r.value))
        return items

    @operation(UserRole.ADMIN)
    async def on_gcsr_select(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        selected = parameters.get("gcsr_select_id", None)
        if selected:
            if "gcsr_current" in parameters:
                if selected in parameters["gcsr_current"]:
                    parameters["gcsr_current"].remove(selected)
                else:
                    parameters["gcsr_current"].append(selected)
            else:
                parameters["gcsr_current"] = [selected]
        await self.to_menu("generate_codes_select_role", context=context)

    @operation(UserRole.ADMIN)
    async def on_generate_codes(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        roles = [UserRole(int(i)) for i in parameters["gcsr_current"]]
        days = int(parameters["generate_codes_select_num_id"])
        num = int(parameters["generate_codes_id"])
        user: User = context.from_user.get_record()
        msg = "⭐ Generated Codes:\n\n"
        for c in to_iterable(user.create_code(roles, days=days, num=num)):
            msg += f"`{c}`\n"
        return msg

    @operation(UserRole.ADMIN)
    async def on_list_group_all(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        sorting, desc = parameters.get("lga_sorting", ("members", True))
        if sorting == "activity":
            groups = Group.select()
            if desc:
                groups = groups.order_by(Group.last_activity.desc())
            else:
                groups = groups.order_by(Group.last_activity)
        else:
            groups = Group.select(Group, fn.COUNT(Member.id).alias("num_members")).join(Member).group_by(Group.id)
            if desc:
                groups = groups.order_by(fn.Count(Member.id).desc())
            else:
                groups = groups.order_by(fn.Count(Member.id))
        items = []
        g: Group
        for i, g in enumerate(groups.iterator()):
            name = f"[{truncate_str(g.title, 20)}](t.me/{g.username})"
            if g.disabled:
                name = f"~~{name}~~"
            item = f"{i+1} | {name}"
            items.append((item, str(i + 1), g.id))
        if not items:
            await self.info("⚠️ No group available.", context=context)
            await self.to_menu("admin", context)
        return items

    @operation(UserRole.ADMIN)
    async def button_lga_switch_activity(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        sorting, desc = parameters.get("lga_sorting", ("members", True))
        if sorting == "activity":
            return "🔽 Sort Activity" if desc else "🔼 Sort Activity"
        else:
            return "↔ Sort Activity"

    @operation(UserRole.ADMIN)
    async def on_lga_switch_activity(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        sorting, desc = parameters.get("lga_sorting", ("members", True))
        if sorting == "activity":
            parameters["lga_sorting"] = ("activity", not desc)
            await context.answer("🔼 Sort oldest to newest" if desc else "🔽 Sort newest to oldest")
        else:
            parameters["lga_sorting"] = ("activity", True)
            await context.answer("🔽 Sort newest to oldest")
        await self.to_menu("list_group_all", context)

    @operation(UserRole.ADMIN)
    async def button_lga_switch_member(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        sorting, desc = parameters.get("lga_sorting", ("members", True))
        if sorting == "members":
            return "🔽 Sort Member Count" if desc else "🔼 Sort Member Count"
        else:
            return "↔ Sort Member Count"

    @operation(UserRole.ADMIN)
    async def on_lga_switch_member(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        sorting, desc = parameters.get("lga_sorting", ("members", True))
        if sorting == "members":
            parameters["lga_sorting"] = ("members", not desc)
            await context.answer("🔼 Sort least member to most" if desc else "🔽 Sort most member to least")
        else:
            parameters["lga_sorting"] = ("members", True)
            await context.answer("🔽 Sort most member to least")
        await self.to_menu("list_group_all", context)

    @operation(UserRole.ADMIN)
    async def on_jump_group_detail_admin(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        parameters["group_id"] = int(parameters["jump_group_detail_admin_id"])
        await self.to_menu("_group_detail_admin", context)

    @operation(UserRole.ADMIN)
    async def on_group_detail_admin(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        group: Group = Group.get_by_id(parameters["group_id"])
        msg = f"ℹ️ Group info:\n\n"
        fields = [
            f"Title: [{group.title}](t.me/{group.username})",
            f"Creator: {group.creator.markdown}",
            f"Members: {group.n_members}",
            f"Messages: {group.n_messages}",
            f"Disabled: {'**Yes**' if group.disabled else 'No'}",
            f"Created: {group.created.strftime('%Y-%m-%d')}",
            f"Last Activity: {group.last_activity.strftime('%Y-%m-%d')}",
        ]
        msg += indent("\n".join(fields), "  ")
        return msg

    @operation(UserRole.ADMIN)
    async def on_admin_delete_group_confirm(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        group: Group = Group.get_by_id(parameters["group_id"])
        return (
            f"⚠️ Are you sure to delete the group [@{group.username}](t.me/{group.username})?\n"
            f"⚠️ This group has {group.n_members} members and {group.n_messages} messages.\n"
            f'⚠️ This group was created at {group.created.strftime("%Y-%m-%d")}.'
        )

    @operation(UserRole.ADMIN)
    async def on_admin_delete_group(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        group: Group = Group.get_by_id(parameters["group_id"])
        group.disabled = True
        group.save()
        await stop_group_bot(group.token)
        await context.answer("✅ Succeed")
        await self.to_menu("_group_detail_admin", context)
