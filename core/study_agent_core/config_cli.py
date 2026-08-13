"""CLI bootstrap that loads config before importing service modules."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from .config import ConfigError, apply_config, load_config


def _parser(service: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", help="Path to non-secret Study Agent config.yaml.")
    parser.add_argument("--profile", help="Configuration profile to apply.")
    parser.add_argument("-h", "--help", action="store_true", help="Show service help.")
    parser.prog = f"study-agent-{service}"
    return parser


def _run(service: str, argv: list[str] | None, start: Callable[[], None]) -> None:
    args, remaining = _parser(service).parse_known_args(argv)
    if args.help:
        _parser(service).print_help()
        return
    if remaining:
        raise SystemExit(f"Unrecognized arguments: {' '.join(remaining)}")
    try:
        config = load_config(args.config, profile=args.profile)
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc
    if config is not None:
        apply_config(config)
    start()


def acp_main(argv: list[str] | None = None) -> None:
    def start() -> None:
        from study_agent_acp.server import main

        main()

    _run("acp", argv, start)


def mcp_main(argv: list[str] | None = None) -> None:
    def start() -> None:
        from study_agent_mcp.server import main

        main()

    _run("mcp", argv, start)
