from __future__ import annotations

from datetime import datetime, timedelta
import random
import string
from typing import Iterable, List, Type, Union

from aenum import IntEnum
from peewee import *

from .utils import to_iterable, extract

db = SqliteDatabase(None)


class OperationError(Exception):
    pass


class UserRoleError(OperationError):
    def __init__(self, roles: Iterable[UserRole], reversed=False):
        displays = [r.display for r in to_iterable(roles)]
        if not reversed:
            if len(displays) == 1:
                super().__init__(f"you must be a/an {displays[0]} to operate")
            else:
                super().__init__(f'you must be one of the {", ".join(displays)}s to operate')
        else:
            if len(displays) == 1:
                super().__init__(f"you are a/an {displays[0]}, so can not operate")
            else:
                super().__init__(f'you are one of the {", ".join(displays)}s, so can not operate')


class MemberRoleError(OperationError):
    def __init__(self, role: MemberRole, reversed=False):
        if not reversed:
            super().__init__(f"you must be a/an {role.display} in this group to operate")
        else:
            super().__init__(f"you are a/an {role.display} in this group, so can not operate")


class BanError(OperationError):
    def __init__(self, type: BanType, member=True, until: datetime = None):
        until_spec = f' until `{until.strftime("%Y-%m-%d %H:%M")}`' if until else ""
        super().__init__(f"{'you can not' if member else 'nobody can'} {type.display} in this group{until_spec}")


class UserRole(IntEnum):
    _init_ = "value display"

    NONE = 0, "unknown user"
    BANNED = 10, "banned user"
    INVITED = 15, "invited user"
    GROUPER = 20, "group creator user"
    AWARDED = 30, "awareded user"
    PAYING = 40, "paying user"
    ADMIN = 90, "system admin"
    CREATOR = 100, "system creator"

class MemberRole(IntEnum):
    _init_ = "value display"

    NONE = 0, "unknown user"
    BANNED = 10, "banned user"
    LEFT = 20, "left user"
    GUEST = 30, "guest"
    MEMBER = 40, "member"
    ADMIN = 60, "admin that can bypass bans"
    ADMIN_MSG = 70, "admin that can pin massages"
    ADMIN_BAN = 80, "admin that can ban others"
    ADMIN_ADMIN = 90, "admin that can set admins and reveal"
    CREATOR = 100, "creator"


class BanType(IntEnum):
    _init_ = "value display"

    NONE = 0, "unknown"
    RECEIVE = 10, "receive messages from others"
    MESSAGE = 20, "send messages"
    MEDIA = 21, "send messages with medias"
    STICKER = 22, "send stickers"
    MARKUP = 23, "send messages with reply markups"
    LONG = 24, "send messages longer than 200 characters"
    LINK = 25, "send messages including links or mentions"
    PIN_MASK = 30, "pin a mask"
    LONG_MASK_1 = 40, "pin a mask longer than 1 emojis"
    LONG_MASK_2 = 41, "pin a mask longer than 2 emojis"
    LONG_MASK_3 = 42, "pin a mask longer than 3 emojis"
    MASK_STR = 43, "pin a mask with non-emojis"
    PM_USER = 50, "pm other user in the group"
    PM_ADMIN = 51, "pm admins in the group"


class EnumField(IntegerField):
    def __init__(self, choices: Type[IntEnum], *args, **kw):
        super(IntegerField, self).__init__(*args, **kw)
        self.choices = choices

    def db_value(self, value: IntEnum):
        return value.value

    def python_value(self, value: int):
        return self.choices(value)


class BaseModel(Model):
    class Meta:
        database = db


class User(BaseModel):
    id = AutoField()
    uid = IntegerField(unique=True)
    username = CharField(index=True, null=True)
    firstname = CharField(index=True, null=True)
    lastname = CharField(index=True, null=True)
    created = DateTimeField(default=datetime.now)

    @property
    def name(self):
        return " ".join([n for n in (self.firstname, self.lastname) if n])

    @property
    def markdown(self):
        return f"[{self.name}](tg://user?id={self.uid})"

    @property
    def masked_name(self):
        ufn = self.firstname
        uln = self.lastname
        if ufn and uln:
            if len(ufn) == 1:
                return "◼" * 2 + uln[-1]
            elif len(uln) == 1:
                return ufn[0] + "◼" * 2
            else:
                return ufn[0] + "◼ ◼" + uln[-1]
        elif ufn:
            return ufn[0] + "◼" * 2
        elif uln:
            return "◼" * 2 + uln[-1]
        else:
            return "◼" * 2

    @property
    def is_banned(self):
        return self.validate(UserRole.BANNED)

    @property
    def is_prime(self):
        return self.validate([UserRole.PAYING, UserRole.AWARDED])

    def roles(self):
        for r in UserRole:
            if self.validate(r):
                yield r

    @classmethod
    def s_all_in_role(cls, roles: Iterable[UserRole]):
        return (
            cls.select()
            .join(Validation)
            .where(Validation.role << to_iterable(roles), (Validation.until > datetime.now()) | (Validation.until.is_null()))
        )

    @classmethod
    def all_in_role(cls, roles: Iterable[UserRole]):
        for u in cls.s_all_in_role(roles).iterator():
            yield u

    @classmethod
    def n_in_role(cls, roles: Iterable[UserRole]):
        return cls.s_all_in_role(roles).count()

    def validate(self, roles: Iterable[UserRole], fail=False, reversed=False):
        if self.s_validation_for(roles).count():
            result = not reversed
        else:
            result = reversed

        if fail and not result:
            raise UserRoleError(roles, reversed=reversed)
        return result

    def s_validation_for(self, roles: Iterable[UserRole] = None):
        if roles is not None:
            return self.validations.where(
                Validation.role << to_iterable(roles), (Validation.until > datetime.now()) | (Validation.until.is_null())
            )
        else:
            return self.validations.where((Validation.until > datetime.now()) | (Validation.until.is_null()))

    def add_validation(
        self,
        roles: Iterable[UserRole],
        days: int = 0,
        from_request: ValidationRequest = None,
    ):
        with db.atomic():
            for role in to_iterable(roles):
                validation: Validation = self.s_validation_for(role).get_or_none()
                if not validation:
                    if days is None:
                        until = None
                    else:
                        until = datetime.now() + timedelta(days=days)
                    validation = Validation(user=self, role=role, until=until)
                else:
                    if days is None:
                        validation.until = None
                    else:
                        validation.until += timedelta(days=days)
                validation.save()
                if from_request:
                    from_request.used = validation
                    from_request.save()

    def remove_validation(self, roles: Iterable[UserRole] = None):
        count = 0
        with db.atomic():
            v: Validation
            for v in self.s_validation_for(roles).iterator():
                v.until = datetime.now()
                v.save()
                count += 1
        return count

    def create_code(
        self,
        roles: Iterable[UserRole],
        days: int = None,
        length: int = 16,
        num: int = 1,
    ) -> Union[List[str], str]:
        codes = []
        with db.atomic():
            for _ in range(num):
                digits = [s for s in string.digits if not s == "0"]
                asciis = [s for s in string.ascii_uppercase if not s == "O"]
                code = "".join(random.choices(digits + asciis, k=length))
                for r in to_iterable(roles):
                    ValidationRequest.create(code=code, role=r, days=days, created_by=self)
                codes.append(code)
        return extract(codes)

    def create_request(self, roles: Iterable[UserRole], days: int = None) -> Union[List[ValidationRequest], ValidationRequest]:
        requests = []
        with db.atomic():
            for r in to_iterable(roles):
                vr = ValidationRequest.create(code=None, role=r, days=days, created_by=self)
                requests.append(vr)
        return extract(requests)

    def add_role(self, roles: Iterable[UserRole], days: int = None):
        with db.atomic():
            for r in to_iterable(roles):
                request = self.create_request(r, days=days)
                self.add_validation(r, days=days, from_request=request)

    def use_code(self, code: str) -> List[ValidationRequest]:
        used = []
        with db.atomic():
            vcs = ValidationRequest.select().where(ValidationRequest.code == code)
            vc: ValidationRequest
            for vc in vcs.iterator():
                if vc.used:
                    continue
                if vc.created_by == self:
                    continue
                if (not vc.role == UserRole.INVITED) and (not vc.created_by.validate(vc.role, fail=False)):
                    continue
                if self.validate(vc.role, fail=False):
                    continue
                if vc.code == code and not vc.used:
                    self.add_validation(vc.role, days=vc.days, from_request=vc)
                    used.append(vc)
        return used

    def member_in(self, group: Group):
        return self.member_profiles.join(Group).where(Group.id == group.id).get_or_none()

    def groups(self, allow_disabled=False, created=False):
        mp: Member
        if created:
            if allow_disabled:
                for g in self.created_groups.iterator():
                    yield g
            else:
                for g in self.created_groups.where(~(Group.disabled)).iterator():
                    yield g
        else:
            if allow_disabled:
                for mp in self.member_profiles.where(Member.role >= MemberRole.GUEST).iterator():
                    yield mp.group
            else:
                for mp in self.member_profiles.where(Member.role >= MemberRole.GUEST).join(Group).where(~(Group.disabled)).iterator():
                    yield mp.group
    
    @property
    def invited_by(self):
        v = self.validations.where(Validation.role == UserRole.INVITED).get_or_none()
        if v:
            vr = v.requests.get_or_none()
            if vr:
                return vr.created_by


class Validation(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="validations")
    role = EnumField(UserRole, default=UserRole.NONE)
    until = DateTimeField(default=datetime.now, null=True)
    created = DateTimeField(default=datetime.now)

    @property
    def by(self):
        results = set()
        r: ValidationRequest
        for r in self.requests.iterator():
            results.add(r.created_by)
        return results


class ValidationRequest(BaseModel):
    id = AutoField()
    code = CharField(null=True)
    role = EnumField(UserRole, default=UserRole.NONE)
    days = IntegerField(null=True)
    created = DateTimeField(default=datetime.now)
    created_by = ForeignKeyField(User, backref="validation_requests")
    used = ForeignKeyField(Validation, backref="requests", null=True, default=None)


class BanGroup(BaseModel):
    id = AutoField()
    created = DateTimeField(default=datetime.now)
    until = DateTimeField(default=datetime.now, null=True)

    default_types = [BanType.LONG_MASK_2, BanType.LONG_MASK_3, BanType.MASK_STR]

    @classmethod
    def generate(cls, types: List[BanType] = None, until: datetime = None):
        if types is None:
            types = cls.default_types
        with db.atomic():
            group = cls.create(until=until)
            for t in to_iterable(types):
                BanGroupEntry.create(type=t, group=group)
        return group


class BanGroupEntry(BaseModel):
    id = AutoField()
    type = EnumField(BanType, default=BanType.NONE)
    group = ForeignKeyField(BanGroup, backref="entries")


class Group(BaseModel):
    id = AutoField()
    uid = IntegerField(index=True)
    token = CharField(max_length=50, unique=True)
    username = CharField(index=True)
    title = CharField(index=True, null=True)
    creator = ForeignKeyField(User, backref="created_groups")
    created = DateTimeField(default=datetime.now)
    last_activity = DateTimeField(default=datetime.now)
    default_ban_group = ForeignKeyField(BanGroup, backref="linked_groups")
    welcome_message = TextField(null=True, default=None)
    welcome_message_photo = TextField(null=True, default=None)
    welcome_message_buttons = TextField(null=True, default=None)
    welcome_latest_messages = BooleanField(default=True)
    chat_instruction = TextField(null=True, default=None)
    disabled = BooleanField(default=False)

    @property
    def n_members(self):
        return self.members.where(Member.role >= MemberRole.GUEST).count()

    @property
    def n_messages(self):
        return self.messages.count()
    
    @property
    def is_prime(self):
        return self.creator.is_prime

    def default_bans(self):
        e: BanType
        for e in self.default_ban_group.entries.iterator():
            yield e.type

    def s_all_has_role(self, role: MemberRole):
        return self.members.where(Member.role >= role, Member.role >= MemberRole.GUEST)

    def all_has_role(self, role: MemberRole):
        for u in self.s_all_has_role(role).iterator():
            yield u

    def user_members(self, users: List[User] = None):
        if users is None:
            m: Member
            for m in self.members.where(Member.role >= MemberRole.GUEST).iterator():
                yield m
        else:
            user_ids = [u.id for u in to_iterable(users)]
            m: Member
            for m in self.members.where(Member.role >= MemberRole.GUEST).join(User).where(User.id << user_ids).iterator():
                yield m

    def member_messages(self, members: List[Member] = None):
        if members is None:
            for m in self.messages.iterator():
                yield m
        else:
            member_ids = [m.id for m in to_iterable(members)]
            m: Message
            for m in self.messages.join(Member).where(Member.id << member_ids).iterator():
                yield m

    def touch(self):
        self.last_activity = datetime.now()
        self.save()

    def cannot(self, ban: BanType, fail=False):
        group_scope: BanGroupEntry = self.default_ban_group.entries.where(BanGroupEntry.type == ban).get_or_none()
        if group_scope:
            if fail:
                raise BanError(type=ban, member=False, until=self.default_ban_group.until)
            return True
        return False


class Member(BaseModel):
    id = AutoField()
    group = ForeignKeyField(Group, backref="members")
    user = ForeignKeyField(User, backref="member_profiles")
    role = EnumField(MemberRole, default=MemberRole.GUEST)
    created = DateTimeField(default=datetime.now)
    last_activity = DateTimeField(default=datetime.now)
    last_mask = CharField(null=True, default=None)
    pinned_mask = CharField(null=True, default=None)
    ban_group = ForeignKeyField(BanGroup, backref="linked_members", null=True)

    @property
    def is_banned(self):
        return not self.validate(MemberRole.BANNED, reversed=True)

    @property
    def n_messages(self):
        return self.messages.count()

    def touch(self):
        self.last_activity = datetime.now()
        self.save()

    def validate(self, role: MemberRole, fail=False, reversed=False):
        if self.user.validate(UserRole.CREATOR, fail=False):
            current_role = MemberRole.ADMIN_ADMIN
        else:
            current_role = self.role
        if not reversed:
            if current_role >= role:
                return True
            else:
                if fail:
                    raise MemberRoleError(role, reversed=False)
                return False
        else:
            if current_role <= role:
                if fail:
                    raise MemberRoleError(role, reversed=True)
                return False
            else:
                return True

    def check_ban(self, ban: BanType, fail=True, check_group=True):
        if self.validate(MemberRole.ADMIN):
            return False
        if self.ban_group:
            member_scope: BanGroupEntry = self.ban_group.entries.where(BanGroupEntry.type == ban).get_or_none()
            if member_scope:
                if fail:
                    raise BanError(type=ban, member=True, until=self.ban_group.until)
                return True
        if check_group:
            group_scope: BanGroupEntry = self.group.default_ban_group.entries.where(BanGroupEntry.type == ban).get_or_none()
            if group_scope:
                if fail:
                    raise BanError(type=ban, member=False, until=self.group.default_ban_group.until)
                return True
        return False
            
    def not_redirected_messages(self, limit: int = 10, days: int = 7):
        results = []
        for m in self.group.messages.order_by(Message.created.desc()).iterator():
            if m.get_redirect_for(self) is None:
                results.append(m)
                if len(results) >= limit:
                    break
                if m.created < datetime.now() - timedelta(days=days):
                    break
            else:
                break
        return results
    
    def not_redirected_pinned_messages(self):
        results = []
        for m in self.group.messages.where(Message.pinned == True).order_by(Message.created.desc()).iterator():
            if m.get_redirect_for(self) is None:
                results.append(m)
            else:
                break
        return results
    
    def s_pinned_messages(self):
        return self.group.messages.where(Message.pinned == True).order_by(Message.created.desc())
    
    def pinned_messages(self):
        for m in self.s_pinned_messages().iterator():
            yield m

class Message(BaseModel):
    id = AutoField()
    group = ForeignKeyField(Group, backref="messages")
    mid = IntegerField(index=True)
    member = ForeignKeyField(Member, backref="messages")
    mask = CharField()
    reply_to = ForeignKeyField('self', backref="replying_messages", null=True)
    pinned = BooleanField(default=False)
    updated = DateTimeField(default=datetime.now)
    created = DateTimeField(default=datetime.now)

    def get_redirect_for(self, member: Member):
        if member.id == self.member.id:
            return self
        else:
            rm: RedirectedMessage = self.redirects.join(Member).where(Member.id == member.id).get_or_none()
            return rm


class RedirectedMessage(BaseModel):
    id = AutoField()
    mid = IntegerField(index=True)
    message = ForeignKeyField(Message, backref="redirects")
    to_member = ForeignKeyField(Member, backref="redirected_messages")
    created = DateTimeField(default=datetime.now)


class PMBan(BaseModel):
    id = AutoField()
    from_member = ForeignKeyField(Member, null=True, backref="pm_bans")
    to_member = ForeignKeyField(Member, backref="applied_pm_bans")
    created = DateTimeField(default=datetime.now)


class PMMessage(BaseModel):
    id = AutoField()
    from_member = ForeignKeyField(Member, null=True, backref="pm_messages")
    to_member = ForeignKeyField(Member, backref="received_pm_messages")
    mid = IntegerField(index=True)
    redirected_mid = IntegerField(index=True)
    time = DateTimeField(default=datetime.now)