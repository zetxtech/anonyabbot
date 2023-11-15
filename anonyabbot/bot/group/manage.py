import asyncio
from datetime import datetime
from textwrap import indent
from pyrogram import Client
from pyrogram.types import Message as TM, CallbackQuery as TC
from pyrubrum import Element

import anonyabbot

from ...utils import truncate_str, parse_timedelta
from ...model import Member, db, MemberRole, Group, BanType, BanGroup
from .common import operation


class Manage:
    @operation(MemberRole.ADMIN)
    async def on_group_details(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        context.parameters.pop("edbg_current", None)
        return (
            f"👑 Welcome group admin {context.from_user.name}.\n\n"
            "👁️‍🗨️ This panel is only visible to you.\n"
            "⬇️ Click the buttons below to configure the group:"
        )

    @operation(MemberRole.ADMIN)
    async def on_group_info(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        group = self.group
        member: Member = context.from_user.get_member(self.group)
        creator = group.creator.markdown if member.role >= MemberRole.ADMIN_BAN else group.creator.masked_name
        waiting_delay = f"{self.worker_status['time'] / self.worker_status['requests']:.1f}" if self.worker_status['requests'] else "inf"
        msg = f"ℹ️ Group info:\n\n"
        fields = [
            f"Title: [{group.title}](t.me/{group.username})",
            f"Creator: {creator}",
            f"Members: {group.n_members}",
            f"Messages: {group.n_messages}",
            f"Average Delay: {waiting_delay} seconds",
            f"Disabled: {'**Yes**' if group.disabled else 'No'}",
            f"Created: {group.created.strftime('%Y-%m-%d')}",
            f"Last Activity: {group.last_activity.strftime('%Y-%m-%d')}",
        ]
        msg += indent("\n".join(fields), "  ")
        return msg

    @operation(MemberRole.ADMIN_BAN)
    async def on_edit_default_ban_group(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        current_selection = parameters.get("edbg_current", None)
        if not current_selection:
            parameters["edbg_current"] = current_selection = [t.value for t in self.group.default_bans()]

        items = []
        types = [t for t in BanType if not t == BanType.NONE]
        for i, t in enumerate(types):
            item = f"{i+1:<2} | {t.display}"
            if t.value in current_selection:
                item = f"`   {item}`"
            else:
                item = f"` ✓ {item}`"
            items.append((item, str(i + 1), t.value))
        return items

    @operation(MemberRole.ADMIN_BAN)
    async def on_edbg_select(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        selected = parameters.get("edbg_select_id", None)
        if selected:
            if "edbg_current" in parameters:
                if selected in parameters["edbg_current"]:
                    parameters["edbg_current"].remove(selected)
                else:
                    parameters["edbg_current"].append(selected)
            else:
                parameters["edbg_current"] = [selected]
        await self.to_menu("edit_default_ban_group", context=context)

    @operation(MemberRole.ADMIN_BAN)
    async def on_edbg_done(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        current_selection = parameters.get("edbg_current", [])
        types = [BanType(v) for v in current_selection]
        with db.atomic():
            original = self.group.default_ban_group
            self.group.default_ban_group = BanGroup.generate(types)
            self.group.save()
            original.delete_instance()
        await context.answer("✅ Succeed.")
        await self.to_menu("_group_details", context)

    @operation(MemberRole.ADMIN_ADMIN)
    async def on_edit_password(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        self.set_conversation(context, "ep_password")
        if self.group.password:
            msg = f"ℹ️ Current group passowrd is `{self.group.password}`"
        else:
            msg = f"ℹ️ Group passowrd is not set. Free to join."
        msg += f"\n\n⬇️ Type your password to set (only visible to you):"
        return msg

    @operation(MemberRole.ADMIN_MSG)
    async def on_edit_welcome_message(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        if self.group.welcome_message:
            msg = f"🧾 Group welcome message is set as:\n\n{self.group.welcome_message}"
        else:
            msg = f"🧾 Group welcome message is not set."
        if self.group.welcome_message_photo:
            msg += f"\n\n🖼️ Group welcome message header image is set."
        if self.group.welcome_message_buttons:
            msg += f"\n\n⌨️ Group welcome message buttons is set."
        msg += "\n\n⬇️ Click the buttons below to configure:"
        return msg

    @operation(MemberRole.ADMIN_MSG)
    async def on_edit_welcome_message_message(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        self.set_conversation(context, "ewmm_message")
        return (
            "⬇️ Type new welcome message (can with images, only visible to the new user):\n\n"
            "ℹ️ Variables:\n"
            "  {name} : User full name\n"
            "  {first_name} : User first name\n"
            "  {last_name}  : User last name\n"
            "  {masked_name}: User masked name\n"
            "  {markdown}   : User full name with mention link\n\n"
            "ℹ️ Type `disable` to disable welcome message."
        )

    @operation(MemberRole.ADMIN_MSG)
    async def on_edit_welcome_message_button(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        self.set_conversation(context, "ewmm_button")
        return (
            "⬇️ Define new welcome message buttons (only visible to you):\n\n"
            "ℹ️ Buttons should be defined in the following format:\n\n"
            "`Button1: https://button1.url | Button2: https://button2.url`\n\n"
            "1. Each line will be a row of buttons.\n"
            "2. Use t.me/username to redirect to a user / group.\n"
        )

    @operation(MemberRole.ADMIN_MSG)
    async def on_ewmb_ok(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        button_spec = parameters["button_spec"]
        test_message_id = parameters["text_message"]
        self.group.welcome_message_buttons = button_spec
        self.group.save()
        await self.bot.delete_messages(self.group.username, test_message_id)
        m = await self.bot.send_message(context.message.chat.id, "✅ Succeed")
        await asyncio.sleep(5)
        await m.delete()
        await context.message.delete()

    @operation(MemberRole.ADMIN_MSG)
    async def on_edit_chat_instruction(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        self.set_conversation(context, "eci_instruction")
        if self.group.chat_instruction:
            msg = f"🧾 Chat instruction is set as:\n\n{self.group.chat_instruction}\n\n"
        else:
            msg = f"🧾 Chat instruction is not set.\n\n"
        msg += (
            "ℹ️ Chat instruction is a note that requires user consent before sending any anonymous message.\n\n"
            "```ℹ️ Example:\n"
            "⭐ Read this before you send your first anonymous message:\n\n"
            "1. Messages will be broadcasted to other members with your identity hidden.\n"
            "2. **DO NOT** delete the message with telegram directly. Instead, use `/delete`.\n"
            "3. If you edited a message, the edition will be broadcasted to all users.\n"
            "4. Have fun chatting!```\n\n"
            "⬇️ Type new chat instruction (only visible to you):\n"
            "ℹ️ (Type `disable` to disable chat instruction)"
        )
        return msg

    @operation(MemberRole.ADMIN_BAN)
    async def on_list_group_members(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        sorting, desc = parameters.get("lgm_sorting", ("role", True))
        members = self.group.members.where(Member.role >= MemberRole.GUEST)
        if sorting == "role":
            if desc:
                members = members.order_by(Member.role.desc())
            else:
                members = members.order_by(Member.role)
        else:
            if desc:
                members = members.order_by(Member.last_activity.desc())
            else:
                members = members.order_by(Member.last_activity)
        items = []
        m: Member
        for i, m in enumerate(members.iterator()):
            item = f"{i+1} | [{truncate_str(m.user.name, 20)}](t.me/{m.user.username})"
            items.append((item, str(i + 1), m.id))
        return items

    @operation(MemberRole.ADMIN_BAN)
    async def button_lgm_switch_activity(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        sorting, desc = parameters.get("lgm_sorting", ("role", True))
        if sorting == "activity":
            return "🔽 Sort Activity" if desc else "🔼 Sort Activity"
        else:
            return "↔ Sort Activity"

    @operation(MemberRole.ADMIN_BAN)
    async def on_lgm_switch_activity(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        sorting, desc = parameters.get("lgm_sorting", ("role", True))
        if sorting == "activity":
            parameters["lgm_sorting"] = ("activity", not desc)
            await context.answer("🔼 Sort oldest to newest" if desc else "🔽 Sort newest to oldest")
        else:
            parameters["lgm_sorting"] = ("activity", True)
            await context.answer("🔽 Sort newest to oldest")
        await self.to_menu("list_group_members", context)

    @operation(MemberRole.ADMIN_BAN)
    async def button_lgm_switch_role(
        self: "anonyabbot.FatherBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        sorting, desc = parameters.get("lgm_sorting", ("role", True))
        if sorting == "role":
            return "🔽 Sort Role" if desc else "🔼 Sort Role"
        else:
            return "↔ Sort Role"

    @operation(MemberRole.ADMIN_BAN)
    async def on_lgm_switch_role(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        sorting, desc = parameters.get("lgm_sorting", ("role", True))
        if sorting == "role":
            parameters["lgm_sorting"] = ("role", not desc)
            await context.answer("🔼 Sort member to admin" if desc else "🔽 Sort admin to member")
        else:
            parameters["lgm_sorting"] = ("role", True)
            await context.answer("🔽 Sort admin to member")
        await self.to_menu("list_group_members", context)

    @operation(MemberRole.ADMIN_BAN)
    async def on_jump_member_detail(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        parameters["member_id"] = int(parameters["jump_member_detail_id"])
        await self.to_menu("_member_detail", context)

    @operation(MemberRole.ADMIN_BAN)
    async def on_member_detail(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        context.parameters.pop("edbg_current", None)
        target: Member = Member.get_by_id(parameters["member_id"])
        return (
            f"👤 Member profile of {target.user.markdown}:\n\n"
            f"ID: {target.user.uid}\n"
            f"Role in group: {target.role.display.title()}\n"
            f"Joining date: {target.created.strftime('%Y-%m-%d')}\n"
            f"Message count: {target.n_messages}\n"
            f"Last Activity: {target.last_activity.strftime('%Y-%m-%d')}\n"
            f"Last Mask: {target.last_mask}\n\n"
            f"👁️‍🗨️ This panel is only visible to you."
        )

    @operation(MemberRole.ADMIN_BAN)
    async def items_edit_member_role_select(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        items = []
        for r in MemberRole:
            button = r.name
            items.append(Element(button, r.value))
        return items

    @operation(MemberRole.ADMIN_BAN)
    async def on_edit_member_role(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        role = MemberRole(int(parameters["edit_member_role_id"]))
        target: Member = Member.get_by_id(parameters["member_id"])
        member: Member = context.from_user.get_member(self.group)
        if target.role >= MemberRole.ADMIN or role >= MemberRole.ADMIN:
            member.validate(MemberRole.ADMIN_ADMIN, fail=True)
        if target.role >= MemberRole.ADMIN_ADMIN:
            member.validate(MemberRole.CREATOR, fail=True)
        if target.id == member.id:
            await context.answer("⚠️ Can not change yourself.")
            await self.to_menu("_member_detail", context)
        if target.role >= member.role:
            await context.answer("⚠️ Permission Denied.")
            await self.to_menu("_member_detail", context)
        target.role = role
        target.save()
        await context.answer("✅ Changed.")
        await self.to_menu("_member_detail", context)

    @operation(MemberRole.ADMIN_BAN)
    async def header_edit_member_ban_group(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        target: Member = Member.get_by_id(parameters["member_id"])
        return f"👤 Set permission for {target.user.markdown}:\n"

    @operation(MemberRole.ADMIN_BAN)
    async def on_edit_member_ban_group(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        target: Member = Member.get_by_id(parameters["member_id"])
        current_selection = parameters.get("embg_current", None)
        if not current_selection:
            if target.ban_group:
                parameters["embg_current"] = current_selection = [t.type.value for t in target.ban_group.entries.iterator()]
            else:
                parameters["embg_current"] = current_selection = [t.value for t in self.group.default_bans()]

        items = []
        types = [t for t in BanType if not t == BanType.NONE]
        for i, t in enumerate(types):
            item = f"{i+1:<2} | {t.display}"
            if t.value in current_selection:
                item = f"`   {item}`"
            else:
                item = f"` ✓ {item}`"
            items.append((item, str(i + 1), t.value))
        return items

    @operation(MemberRole.ADMIN_BAN)
    async def on_embg_select(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        selected = parameters.get("embg_select_id", None)
        if selected:
            if "embg_current" in parameters:
                if selected in parameters["embg_current"]:
                    parameters["embg_current"].remove(selected)
                else:
                    parameters["embg_current"].append(selected)
            else:
                parameters["embg_current"] = [selected]
        await self.to_menu("edit_member_ban_group", context=context)

    @operation(MemberRole.ADMIN_BAN)
    async def items_edit_member_ban_group_select_time(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        return [Element(i, i) for i in ["1m", "10m", "1h", "12h", "1d", "3d", "5d", "10d", "30d", "180d", "1y", "10y"]]

    @operation(MemberRole.ADMIN_BAN)
    async def on_embg_done(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        target: Member = Member.get_by_id(parameters["member_id"])
        member: Member = context.from_user.get_member(self.group)
        if target.role >= MemberRole.ADMIN:
            member.validate(MemberRole.ADMIN_ADMIN, fail=True)
        if target.role >= MemberRole.ADMIN_ADMIN:
            member.validate(MemberRole.CREATOR, fail=True)
        if target.id == member.id:
            await context.answer("⚠️ Can not change yourself.")
            await self.to_menu("_member_detail", context)
        if target.role >= member.role:
            await context.answer("⚠️ Permission Denied.")
            await self.to_menu("_member_detail", context)

        current_selection = parameters.get("embg_current", [])
        td_str = parameters["embg_done_id"]
        td = parse_timedelta(td_str)
        until = datetime.now() + td
        types = [BanType(v) for v in current_selection]
        with db.atomic():
            original = target.ban_group
            target.ban_group = BanGroup.generate(types, until=until)
            target.save()
            if original:
                original.delete_instance()
        await context.answer("✅ Succeed.")
        await self.to_menu("_member_detail", context)

    @operation(MemberRole.ADMIN_BAN)
    async def on_kick_member_confirm(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        target: Member = Member.get_by_id(parameters["member_id"])
        return (
            f"⚠️ Are you sure to kick the member {target.user.markdown}?\n"
            f"⚠️ This member is currently a {target.role.display}.\n"
            f"⚠️ This member has sent {target.n_messages} messages.\n"
        )

    @operation(MemberRole.ADMIN_BAN)
    async def on_kick_member(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        target: Member = Member.get_by_id(parameters["member_id"])
        member: Member = context.from_user.get_member(self.group)
        if target.role >= MemberRole.ADMIN:
            member.validate(MemberRole.ADMIN_ADMIN, fail=True)
        if target.role >= MemberRole.ADMIN_ADMIN:
            member.validate(MemberRole.CREATOR, fail=True)
        if target.id == member.id:
            await context.answer("⚠️ Can not change yourself.")
            await self.to_menu("_member_detail", context)
        if target.role >= member.role:
            await context.answer("⚠️ Permission Denied.")
            await self.to_menu("_member_detail", context)
        target.role = MemberRole.BANNED
        target.save()
        await context.answer("✅ Succeed.")
        await self.to_menu("list_group_members", context)

    @operation(MemberRole.ADMIN)
    async def on_close_group_details(
        self: "anonyabbot.GroupBot",
        handler,
        client: Client,
        context: TC,
        parameters: dict,
    ):
        await context.message.delete()
        await context.answer("✅ Closed.")
