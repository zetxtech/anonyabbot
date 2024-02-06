import asyncio
from datetime import datetime, timedelta
import random
from typing import Dict, Tuple

import emoji

from ...model import Member
from ...cache import CacheDict


class MaskNotAvailable(Exception):
    pass


class UniqueMask:
    emojis = emoji.distinct_emoji_list(
        "🐶🐱🐹🐰🦊🐼🐯🐮🦁🐸🐵🐔🐧🐥🦆🦅🦉🦄🐝🦋🐌🐙🦖"
        "🦀🐠🐳🐘🐿👻🎃🦕🐡🎄🍄🍁🐚🧸🎩🕶🐟🐬🦁🐲🚤🛶🦞"
        "🦑🎄🐚👽🎃🧸♠️♣️♥️♦️🃏🔮🛸⛵️🎲🧊🍩🍪🍭🌶🍗🍖☘️🍄🤡"
        "🧩🌀🏮🪄🏀⚽️🏈🎱🪁🍥🍦🧁🍓🫐🍇🍉🍋🍐🍎🍒🍑🥝🍆"
        "🥑🥕🌽🥐🎷♟🏖🏔⚓️🛵🔯☮️☯️🆙🏴‍☠️⏳⛩🦧🌴🌷🌞🧶🐳🧿"
    )

    def __init__(self, token: str):
        self.lock = asyncio.Lock()
        self.token = token
        self.users: Dict[int, str] = CacheDict(f'group.{self.token}.unique_mask.users')
        self.masks: Dict[str, Tuple[int, datetime]] = CacheDict(f'group.{self.token}.unique_mask.masks')

    def save(self):
        self.users.save()
        self.masks.save()

    async def take_mask(self, member: Member, role: str):
        async with self.lock:
            if role in self.masks:
                uid, t = self.masks[role]
                if t > (datetime.now() + timedelta(days=3)):
                    return False
                else:
                    del self.users[uid]
            self.users[member.id] = role
            self.masks[role] = (member.id, datetime.now())
            return True   

    async def has_mask(self, member: Member):
        async with self.lock:
            return member.id in self.users

    async def mask_for(self, member: Member):
        async with self.lock:
            if member.id in self.users:
                return self.users[member.id]
            else:
                return None

    async def get_mask(self, member: Member, renew=False):
        async with self.lock:
            if member.id in self.users:
                if renew:
                    old_role = self.users[member.id]
                    role = self._get_mask()
                    self.users[member.id] = role
                    del self.masks[old_role]
                    self.masks[role] = (member.id, datetime.now())
                    self.save()
                    return True, role
                else:
                    role = self.users[member.id]
                    self.masks[role] = (member.id, datetime.now())
                    self.save()
                    return False, role
            else:
                role = self._get_mask()
                self.users[member.id] = role
                self.masks[role] = (member.id, datetime.now())
                self.save()
                return True, role

    def _get_mask(self):
        unused = [e for e in self.emojis if e not in self.masks.keys()]
        if unused:
            return random.choice(unused)
        oldest_avail_role = None
        oldest_avail_timestamp = None
        for role, (uid, t) in self.masks.items():
            if t > (datetime.now() + timedelta(days=3)):
                continue
            if (not oldest_avail_role) or (t < oldest_avail_timestamp):
                oldest_avail_role = role
                oldest_avail_timestamp = t
        if oldest_avail_role:
            uid, _ = self.masks[oldest_avail_role]
            del self.users[uid]
            return oldest_avail_role
        else:
            raise MaskNotAvailable()
