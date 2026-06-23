"""MCP tool definitions and handlers."""
import json

import mcp.types as types
from mcp.server import Server


def register_tools(server: Server, tg, whitelist) -> None:

    @server.list_tools()
    async def _list_tools():
        return [
            types.Tool(
                name="tg_list_folders",
                description=(
                    "List all Telegram folder filters (the custom tabs in the sidebar). "
                    "Returns id and name for each folder. "
                    "Use these IDs to configure the whitelist or filter other tools."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="tg_list_dialogs",
                description=(
                    "List accessible Telegram dialogs (chats, groups, channels) "
                    "with their IDs, types, and unread counts. "
                    "Respects the whitelist when configured; returns all dialogs when whitelist is empty "
                    "(useful for initial setup). Optionally limit to a specific folder."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "folder_id": {
                            "type": "integer",
                            "description": "Limit to dialogs inside this folder (ID from tg_list_folders).",
                        }
                    },
                },
            ),
            types.Tool(
                name="tg_get_messages",
                description=(
                    "Read messages from a specific chat. Never marks messages as read. "
                    "Requires the chat to be in the whitelist. "
                    "chat_ref accepts: numeric ID, @username, or a t.me link "
                    "(https://t.me/c/CHANNELID/MSGID or https://t.me/username)."
                ),
                inputSchema={
                    "type": "object",
                    "required": ["chat_ref"],
                    "properties": {
                        "chat_ref": {
                            "type": "string",
                            "description": "Chat to read: numeric ID, @username, or https://t.me/... link.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max messages to return (default 50, max 200).",
                            "default": 50,
                        },
                        "unread_only": {
                            "type": "boolean",
                            "description": "Return only unread messages (default false).",
                            "default": False,
                        },
                        "since_hours": {
                            "type": "number",
                            "description": "Return only messages sent within the last N hours.",
                        },
                        "since_message_id": {
                            "type": "integer",
                            "description": "Return only messages with ID strictly greater than this value.",
                        },
                    },
                },
            ),
            types.Tool(
                name="tg_get_unread_summary",
                description=(
                    "Get a digest of unread messages across all whitelisted chats, "
                    "optionally scoped to a folder. "
                    "For each chat with unread messages, returns the last N messages. "
                    "Never marks messages as read."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "folder_id": {
                            "type": "integer",
                            "description": "Scope to a specific folder (ID from tg_list_folders).",
                        },
                        "max_messages_per_chat": {
                            "type": "integer",
                            "description": "Max messages to return per chat (default 20).",
                            "default": 20,
                        },
                    },
                },
            ),
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict):
        try:
            if name == "tg_list_folders":
                data = await tg.get_folders()

            elif name == "tg_list_dialogs":
                folder_id = arguments.get("folder_id")
                data = await tg.get_dialogs(folder_id=folder_id, whitelist=whitelist)

            elif name == "tg_get_messages":
                data = await tg.get_messages(
                    chat_ref=arguments["chat_ref"],
                    limit=int(arguments.get("limit", 50)),
                    unread_only=bool(arguments.get("unread_only", False)),
                    since_hours=arguments.get("since_hours"),
                    since_message_id=arguments.get("since_message_id"),
                    whitelist=whitelist,
                )

            elif name == "tg_get_unread_summary":
                data = await tg.get_unread_summary(
                    folder_id=arguments.get("folder_id"),
                    max_per_chat=int(arguments.get("max_messages_per_chat", 20)),
                    whitelist=whitelist,
                )

            else:
                return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(data, ensure_ascii=False, indent=2),
                )
            ]

        except PermissionError as exc:
            return [types.TextContent(type="text", text=f"Access denied: {exc}")]
        except Exception as exc:
            return [types.TextContent(type="text", text=f"Error ({type(exc).__name__}): {exc}")]
