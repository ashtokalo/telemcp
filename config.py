"""Configuration loader for telemcp."""
import json
import os
import sys

TELEGRAM_DESKTOP_API_ID = 2040
TELEGRAM_DESKTOP_API_HASH = "b18441a1ff607e10a989891a5462e627"

BUILTIN_CREDS_WARNING = """\
[telemcp] WARNING: api_id/api_hash not set — falling back to Telegram Desktop credentials.
Risks:
  • Telegram may flag the session if its behavior deviates from the real Desktop client.
  • In rare cases, third-party api_id usage has led to temporary account restrictions.
  • For low-volume, read-only personal use the risk is minimal but non-zero.
  • To eliminate the risk entirely, register your own app at https://my.telegram.org
"""


class Config:
    def __init__(self, data: dict):
        api_id = data.get("api_id")
        api_hash = data.get("api_hash")

        if not api_id or not api_hash:
            print(BUILTIN_CREDS_WARNING, file=sys.stderr, flush=True)
            self.api_id = TELEGRAM_DESKTOP_API_ID
            self.api_hash = TELEGRAM_DESKTOP_API_HASH
        else:
            self.api_id = int(api_id)
            self.api_hash = str(api_hash)

        session = data.get("session_file", "~/.telemcp/session")
        self.session_file = os.path.expanduser(session)

        wl = data.get("whitelist") or {}
        self.whitelist = {
            "folders":  list(wl.get("folders", [])),
            "groups":   list(wl.get("groups", [])),
            "accounts": list(wl.get("accounts", [])),
        }

        self.proxy = data.get("proxy") or None

    @classmethod
    def load(cls, path: str) -> "Config":
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"[telemcp] Config file not found: {path}", file=sys.stderr)
            print(f"[telemcp] Copy config.example.json to {path} and edit it.", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"[telemcp] Invalid JSON in {path}: {e}", file=sys.stderr)
            sys.exit(1)
        return cls(data)
