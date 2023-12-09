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
            M("start", default=True): {
                M("my_info", "ℹ️ Profile"): {
                    M("create_code", "🔗 Create Invite Link"): None,
                    M("use_code", "🗝️ Redeem Code"): None,
                },
                M("new_group", "💬 New Group"): {L("botfather", "Go to @botfather", url="t.me/botfather")},
                P(
                    "list_group",
                    "⚒️ My Groups",
                    "ℹ️ Created Groups:",
                    extras="new_group",
                ): {M("jump_group_detail")},
                L("feedback_group", "💬 Feedback", url="t.me/anonyabbot_chat_bot"): None,
            },
            M("_group_detail", back="list_group"): {
                M("edit_group_profile", "⚒️ Group Profile", "ℹ️ Group avatar and description can only be edited in @botfather"): {
                    L("botfather_group", "Go to @botfather", url="t.me/botfather")
                },
                M("delete_group_confirm", "🗑️ Delete Group"): {M("delete_group", "⚠️ Yes, I am sure.")},
            },
            M("admin"): {
                K("generate_codes_select_role", "👑 Generate Code", "ℹ️ Select Roles", extras="_generate_codes_select_days"): {
                    M("gcsr_select")
                },
                P(
                    "list_group_all",
                    "⚒️ Manage Groups",
                    "ℹ️ All Groups:",
                    extras=["_lga_switch_activity", "_lga_switch_member"],
                ): {M("jump_group_detail_admin")},
            },
            K("_generate_codes_select_days", display="ℹ️ Select Time", items=[30, 60, 90, 180, 360, 1080, 3600]): {
                K("generate_codes_select_num", display="ℹ️ Select Quantity", items=[1, 5, 10, 20]): {M("generate_codes", back="admin")}
            },
            M("_lga_switch_activity"): None,
            M("_lga_switch_member"): None,
            M("_group_detail_admin", back="list_group_all"): {
                M("admin_delete_group_confirm", "🗑️ Delete Group"): {M("admin_delete_group", "⚠️ Yes, I am sure.")},
            },
        }

        return transform(menu)
