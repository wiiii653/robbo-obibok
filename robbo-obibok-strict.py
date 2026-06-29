"""Strict-compatibility launcher facade for the robbo-obibok runtime module."""

from __future__ import annotations

from robbo_obibok_cli import run_runtime_entrypoint


def main() -> None:
    run_runtime_entrypoint(strict=True)


if __name__ == "__main__":
    main()
