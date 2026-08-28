"""Minimal thin terminal client.

Start the server, then run:
    rpg-engine play <actor-id>

This module is kept as a discoverable example and delegates to the installed CLI.
"""

from rpg_engine_api.cli import main


if __name__ == "__main__":
    main()
