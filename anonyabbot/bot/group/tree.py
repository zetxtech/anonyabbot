from pyrubrum import transform

import anonyabbot


class Tree:
    @property
    def tree(self: "anonyabbot.FatherBot"):
        M = self._menu
        L = self._link
        P = self._page
        K = self._keyboard
        menu = {
            M("_chat_instruction"): {M("chat_instruction_confirm", "✅ I have carefully read and accept.")},
            M("start"): {
                M("leave_group_confirm", "⏏️ Leave Group"): {M("leave_group", "⚠️ Yes, I am sure.")},
                M("manage_group", "⚒️ Manage Group"): None,
                M("close_start", "❌ Close"): None,
            },
            M("_group_details"): {
                M("group_info", "ℹ️ Group Info"): None,
                M("edit_group_profile", "⚒️ Group Profile", "ℹ️ Group avatar and description can only be edited in @botfather"): {
                    L("botfather_group", "Go to @botfather", url="t.me/botfather")
                },
                P(
                    "edit_default_ban_group",
                    "👑 Default Permissions",
                    "👤 Default permission for all members:\n",
                    extras="_edbg_done",
                    per_page=8,
                ): {M("edbg_select")},
                M("edit_welcome_message", "⭐ Welcome Message", per_line=1): {
                    M("edit_welcome_message_message", "🧾 Edit Message"),
                    M("edit_welcome_message_button", "⌨️ Edit Buttons"),
                    M("toggle_latest_message"),
                },
                M("edit_chat_instruction", "🧾 Chatting Instruction"): None,
                P("list_group_members", "👤 Members", extras=["_lgm_switch_activity", "_lgm_switch_role"]): {M("jump_member_detail")},
                M("close_group_details", "❌ Close"): None,
            },
            M("_edbg_done"): None,
            M("_lgm_switch_activity"): None,
            M("_lgm_switch_role"): None,
            M("_member_detail", back="list_group_members"): {
                K("edit_member_role_select", "👑 Edit Role", "👑 Select Roles"): {M("edit_member_role")},
                P("edit_member_ban_group", "⚠️ Edit Permission", extras="_edit_member_ban_group_select_time"): {M("embg_select")},
                M("kick_member_confirm", "🚫 Kick Member"): {M("kick_member", "⚠️ Yes, I am sure.")},
            },
            K("_edit_member_ban_group_select_time", display="ℹ️ Select Time"): {
                M("embg_done"): None,
            },
            M("_ewmb_ok_confirm", display="❓ Is this correct?"): {M("_ewmb_ok", "✅ Yes", back=False)},
        }

        return transform(menu)
