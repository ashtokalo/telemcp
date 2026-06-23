"""Entry point for `python -m telemcp` and the `telemcp` console script."""
import sys


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else None

    if cmd == "auth":
        sys.argv = [sys.argv[0] + " auth"] + sys.argv[2:]
        from .auth import main as auth_main
        auth_main()
    elif cmd == "connection":
        sys.argv = [sys.argv[0] + " connection"] + sys.argv[2:]
        from .test_connection import main as connection_main
        connection_main()
    else:
        from .server import run
        run()


if __name__ == "__main__":
    main()
