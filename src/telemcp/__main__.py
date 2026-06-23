"""Entry point for `python -m telemcp` and the `telemcp` console script."""
import sys

from .cli import main as _cli_main
from .server import run


def main() -> None:
    # If first argument is not a known CLI command, start the MCP server.
    # This lets `telemcp` (no args) work as a server for MCP clients.
    cli_commands = {"auth", "connection", "folders", "dialogs", "messages", "unread",
                    "--help", "-h", "--version"}
    if len(sys.argv) == 1 or sys.argv[1] not in cli_commands:
        run()
    else:
        _cli_main()


if __name__ == "__main__":
    main()
