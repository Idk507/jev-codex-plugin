"""Run the JEV MCP server over stdio."""

from .server import create_server


def main() -> None:
    """Start the local stdio MCP server."""
    create_server().run()


if __name__ == "__main__":  # pragma: no cover - exercised by MCP host
    main()
