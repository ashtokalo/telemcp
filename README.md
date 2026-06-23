# telemcp

An MCP server that gives AI assistants read-only access to your personal Telegram account.
It connects via MTProto (as a regular client, not a bot), enforces a whitelist of allowed
chats, and never marks messages as read.

Typical use cases:

- "Summarize unread messages in the XXXXXX folder."
- "What errors appeared in this log channel in the last 24 hours?" (given a t.me link or name)

## Requirements

- Python 3.8+
- A Telegram account
- Telegram API credentials (see below)

## Installation

```bash
pip install -r requirements.txt
```

## API credentials

Telegram requires an `api_id` and `api_hash` to identify the client application.
You can get your own for free at https://my.telegram.org - go to "API development tools"
and create an application. The name and platform do not matter.

If you leave `api_id` and `api_hash` empty in the config, the server falls back to
Telegram Desktop's public credentials. This works but carries a small risk: Telegram
may flag or restrict the session if its behavior does not match the real Desktop client.
For low-volume personal use the risk is minimal. The server prints a warning on startup
when using the fallback credentials.

## Setup

**1. Copy the example config and edit it.**

```bash
cp config.example.json config.json
```

**2. Run the auth script once.** It connects to Telegram, asks for your phone number
and the confirmation code, and saves the session to disk.

```bash
python auth.py --config config.json
```

If two-factor authentication is enabled on your account, it will also ask for the password.
After this step, the session file handles authentication and no interactive input is needed.

**3. Configure the whitelist.** Start the server and use `tg_list_folders` and
`tg_list_dialogs` to find the IDs of the folders and chats you want to allow, then add
them to `config.json`.

**4. Register the server in your MCP client** (e.g. Claude Code `.mcp.json`):

```json
{
  "mcpServers": {
    "telegram": {
      "command": "python",
      "args": ["/path/to/telemcp/server.py", "--config", "/path/to/config.json"]
    }
  }
}
```

## Configuration reference

All fields are optional except as noted.

```json
{
  "api_id": 12345,
  "api_hash": "abcdef1234567890abcdef1234567890",

  "session_file": "~/.telemcp/session",

  "whitelist": {
    "folders":  [2, 5],
    "groups":   [-1001234567890, "@some_channel"],
    "accounts": [123456789, "@friend"]
  },

  "proxy": {
    "type":     "socks5",
    "host":     "127.0.0.1",
    "port":     1080,
    "username": null,
    "password": null
  }
}
```

### api_id, api_hash

Your Telegram application credentials from https://my.telegram.org.
Set to `null` or omit to use the Telegram Desktop fallback (see above).

### session_file

Path to the Telethon session file. Created by `auth.py`. Supports `~` expansion.
Default: `~/.telemcp/session`.

### whitelist

Controls which chats the server will read from.

- `folders` - list of Telegram folder IDs. All chats inside the folder are allowed.
- `groups` - list of group or channel identifiers (numeric IDs or @usernames).
- `accounts` - list of user identifiers for private conversations (numeric IDs or @usernames).

Numeric group and channel IDs are negative (e.g. `-1001234567890`).
Use `tg_list_folders` and `tg_list_dialogs` to find IDs.

When the whitelist is empty, `tg_list_folders` and `tg_list_dialogs` still work
(so you can discover IDs), but `tg_get_messages` and `tg_get_unread_summary`
will refuse all requests.

### proxy

Optional. Supported types:

**SOCKS5 or SOCKS4:**

```json
"proxy": {
  "type":     "socks5",
  "host":     "127.0.0.1",
  "port":     1080,
  "username": null,
  "password": null
}
```

**HTTP:**

```json
"proxy": {
  "type": "http",
  "host": "proxy.example.com",
  "port": 8080,
  "username": null,
  "password": null
}
```

**MTProto proxy:**

```json
"proxy": {
  "type":   "mtproto",
  "host":   "proxy.example.com",
  "port":   443,
  "secret": "dd1234abcdef..."
}
```

Set to `null` to connect directly.

## Available tools

### tg_list_folders

Returns all Telegram folder filters (the custom tabs in the sidebar) with their IDs and names.
Use the IDs to populate `whitelist.folders` in the config.

### tg_list_dialogs

Returns accessible dialogs (chats, groups, channels) with ID, name, type, unread count,
and last message date. Respects the whitelist when configured; returns all dialogs when
the whitelist is empty, which is useful for initial setup.

Optional parameter: `folder_id` - limit results to a specific folder.

### tg_get_messages

Reads messages from a single chat. Never marks them as read. The chat must be in the whitelist.

Parameters:

| Name | Type | Default | Description |
|---|---|---|---|
| `chat_ref` | string | required | Numeric ID, @username, or t.me link |
| `limit` | integer | 50 | Max messages to return (hard cap: 200) |
| `unread_only` | boolean | false | Return only unread messages |
| `since_hours` | number | - | Return only messages from the last N hours |
| `since_message_id` | integer | - | Return only messages with ID greater than this value |

Accepted `chat_ref` formats:

- `-1001668839992` - numeric channel ID
- `@username` - public username
- `https://t.me/c/1668839992/5699` - private channel link (message ID is ignored, only the channel ID is used)
- `https://t.me/username` - public channel link

### tg_get_unread_summary

Returns a digest of unread messages across all whitelisted chats. For each chat with
unread messages, returns the most recent N messages. Does not mark anything as read.

Optional parameters:

- `folder_id` - scope to a specific folder
- `max_messages_per_chat` - messages per chat (default: 20)

## What this server does not do

- Send messages
- Mark messages as read
- Download media files (text and captions only)
- Edit or delete messages
- Manage contacts, groups, or channels
