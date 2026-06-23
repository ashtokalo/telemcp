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
make configure
```

This creates `.venv` and installs all dependencies including dev tools. Equivalent to:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

On most modern Linux distributions and macOS, system Python is managed externally and
`pip install` into the system environment is blocked — always use a virtual environment.

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

**2. Authenticate once.** The auth script connects to Telegram and saves the session to disk.
After this step, the session file handles all authentication automatically.

Two login methods are available:

**Phone + code** - Telegram sends a confirmation code to your other devices:

```bash
make auth-phone
```

Enter your phone number with country code (e.g. `+79001234567`) and the code that arrives
in Telegram. If two-factor authentication is enabled, it also asks for the password.

**QR code** - no SMS or code needed; scan with an existing Telegram client:

```bash
make auth-qr
```

A QR code is printed to the terminal. On your phone or desktop Telegram, go to
Settings -> Devices -> Link Desktop Device, then scan the code. If two-factor authentication
is enabled, it prompts for the password after scanning.

Use `make auth-qr` if codes sent to your devices are not arriving, or to avoid phone-based verification.

To see full Telethon protocol logs during auth (useful for debugging):

```bash
.venv/bin/python -m telemcp.auth --config config.json --verbose
```

**3. Verify the connection.** After authentication, run the smoke test to confirm everything works:

```bash
make connection
```

It connects to Telegram, prints all folders and the first 15 dialogs, and if a whitelist is
configured, also shows dialogs passing the whitelist filter. A successful run looks like:

```
Connecting to Telegram...
OK

Folders:
   2  Family
   5  Work

First 15 dialogs (no whitelist filter):
      -1001234567890  supergroup   Team Chat  [3 unread]
             9876543  user         John Smith
  ...
```

**4. Configure the whitelist.** Start the server and use `tg_list_folders` and
`tg_list_dialogs` to find the IDs of the folders and chats you want to allow, then add
them to `config.json`.

**5. Register the server in your MCP client.**

Via Claude Code CLI (simplest):

```bash
claude mcp add telegram /path/to/telemcp/telemcp.sh --config /path/to/config.json
```

Or manually in `.mcp.json`:

```json
{
  "mcpServers": {
    "telegram": {
      "command": "/path/to/telemcp/telemcp.sh",
      "args": ["--config", "/path/to/telemcp/config.json"]
    }
  }
}
```

`telemcp.sh` uses Python from `.venv` inside the telemcp directory if it exists, otherwise
falls back to the system `python3`.

## Config file lookup order

When `--config` is a relative path (or omitted, defaulting to `config.json`), the server
resolves it in this order:

1. Next to the script itself: `<telemcp dir>/config.json`
2. In the user config directory: `~/.telemcp/config.json`

If neither location has the file, the server exits with an error. Absolute paths bypass
this lookup and are used as-is.

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

## Session encryption

By default, the Telethon session is stored as a plain SQLite file on disk. To encrypt it,
set the `TELEMCP_PINCODE` environment variable before running `auth.py` and the server.

```bash
export TELEMCP_PINCODE="your-passphrase"
make auth-phone   # or make auth-qr
```

When the variable is set:

- `auth.py` exports the session as a string, encrypts it with Fernet (AES-128-CBC + HMAC-SHA256,
  key derived via PBKDF2-HMAC-SHA256 with 200 000 iterations), and saves it to
  `<session_file>.enc`. The plain SQLite file is deleted.
- The server loads the encrypted file into memory on startup and saves it back on shutdown.
  The plain session file is never written to disk.

The `.enc` file is useless without the passphrase.

If `TELEMCP_PINCODE` is not set, the server falls back to the plain SQLite session with no
change in behavior.

### Passing the pin to Claude Code

In `.mcp.json`, use the `env` field:

```json
{
  "mcpServers": {
    "telegram": {
      "command": "/path/to/telemcp/telemcp.sh",
      "args": ["--config", "/path/to/telemcp/config.json"],
      "env": {
        "TELEMCP_PINCODE": "your-passphrase"
      }
    }
  }
}
```

Via CLI (`claude mcp add` does not support `env` directly — edit `.mcp.json` after adding):

```bash
claude mcp add telegram /path/to/telemcp/telemcp.sh --config /path/to/telemcp/config.json
# then open .mcp.json and add the "env" block manually
```

## Running tests

```bash
make test
```

Tests cover config loading and path resolution, whitelist filtering, session encryption
round-trips, and URL/chat-ref parsing. They run without a Telegram connection.

To run a specific file or test:

```bash
.venv/bin/pytest tests/test_session.py -v
.venv/bin/pytest tests/ -k "wrong_pin" -v
```

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
