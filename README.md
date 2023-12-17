## Anonyabbot

**Anonyabbot** is a bot for creating fully anonymous groups. ([@anonyabbot](https://t.me/anonyabbot)).

[![Screenshot](https://github.com/anonyabbot/.github/raw/main/images/button.svg)](https://t.me/anonyabbot)

### Features
1. Anonymous groups are created as bots, where messages are broadcasted to all members.
2. All identities are hidden, including name, username, avatar, online status, input status, etc.
3. User will be identified with a mask (emoji or multiple emojis).
4. Built-in management tools are included, such as banning, welcome message, pinned messages, etc.
5. Message ids, rather than message content, are stored by the bot only.

### Usage
Goto [@anonyabbot](https://t.me/anonyabbot), then follow the instructions in the bot. In brief:
1. Click `New Group` in [@anonyabbot](https://t.me/anonyabbot).
2. Create a new bot in [@botfather](https://t.me/botfather), and forward the token to [@anonyabbot](https://t.me/anonyabbot).
3. Your masquerade is set.

### Deploy by yourself

The version on Github might be lagging behind the version used by [@anonyabbot](https://t.me/anonyabbot).

1. Clone the repo:

```bash
git clone https://github.com/anonyabbot/anonyabbot.git
```

2. Create a `config.toml`:

```toml
[tele]
api_id = "12345678"
api_hash = "abcde1234567890abcde1234567890"

[father]
token = "12345678:AbCdEfG-123456789"
```

3. Create an python environment and install:

```bash
python -m venv venv
. venv/bin/activate
pip install -e .
```

4. Start bot server:

```bash
anonyabbot config.toml
```

Your self-deployed version SHOULD clearly identify this repository on `/start`. Thanks.
