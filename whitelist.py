"""Whitelist filtering — which chats/folders are accessible."""


class Whitelist:
    def __init__(self, config: dict):
        self.folder_ids: set = set(int(x) for x in config.get("folders", []))

        groups = config.get("groups", [])
        self._group_ids: set = {int(x) for x in groups if str(x).lstrip("-").isdigit()}
        self._group_names: set = {
            str(x).lstrip("@").lower() for x in groups if not str(x).lstrip("-").isdigit()
        }

        accounts = config.get("accounts", [])
        self._account_ids: set = {int(x) for x in accounts if str(x).lstrip("-").isdigit()}
        self._account_names: set = {
            str(x).lstrip("@").lower() for x in accounts if not str(x).lstrip("-").isdigit()
        }

    def is_configured(self) -> bool:
        return bool(
            self.folder_ids
            or self._group_ids
            or self._group_names
            or self._account_ids
            or self._account_names
        )

    def allows_direct(self, entity_id: int, username: str = None) -> bool:
        """Check if an entity is directly whitelisted by ID or username."""
        if entity_id in self._group_ids or entity_id in self._account_ids:
            return True
        if username:
            un = username.lstrip("@").lower()
            if un in self._group_names or un in self._account_names:
                return True
        return False

    def allows_folder(self, folder_id: int) -> bool:
        return folder_id in self.folder_ids
