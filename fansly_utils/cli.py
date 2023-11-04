from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING
import os

if TYPE_CHECKING:
    from argparse import _SubParsersAction

__all__ = ["get_cli_arg_parser"]


def _is_valid_path(file_path: str) -> Path:
    path = Path(file_path)
    if path.exists():
        return path
    else:
        raise FileNotFoundError(file_path)


def _to_log_level(value: str) -> str:
    return value.removesuffix("s").upper()


class FileType(IntEnum):
    NONE = 1,
    INPUT = 2,
    OUTPUT = 3


_DEFAULT_FILE: Path = Path("fansly-backup.json")


def _add_parser(
    subparsers: "_SubParsersAction[ArgumentParser]",
    name: str,
    help: str,
    file_type: FileType = FileType.OUTPUT
) -> ArgumentParser:
    parser = subparsers.add_parser(
        name,
        help=help,
        description=help,
        formatter_class=ArgumentDefaultsHelpFormatter)

    if file_type == FileType.INPUT:
        parser.add_argument(
            "file",
            nargs="?",
            type=_is_valid_path,
            help="A path to a JSON file with previously saved data.",
            default=_DEFAULT_FILE,
        )
    elif file_type == FileType.OUTPUT:
        parser.add_argument(
            "file",
            nargs="?",
            help="A path to an output JSON file.",
            default=_DEFAULT_FILE,
        )

    parser.add_argument(
        "-c",
        "--config",
        type=_is_valid_path,
        help="A path to configuration INI file.",
        default="config.ini",
    )

    log_levels = parser.add_mutually_exclusive_group()
    log_levels.add_argument(
        "-l",
        "--log-level",
        choices=["debug", "info", "warnings", "errors"],
        type=_to_log_level,
        help="Set desired log level.",
        default="info",
    )
    log_levels.add_argument(
        "-w",
        "--warnings",
        help="Enable only warnings of higher log entries.",
        action="store_true",
    )

    return parser



def get_cli_arg_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="A set of useful utils for dumping, restoring and wiping your fansly.com account data."
    )
    subparsers = parser.add_subparsers(dest='command')

    # backup

    backup = _add_parser(subparsers, "backup", "Backup followings, notes and user lists.", FileType.INPUT)
    backup.add_argument(
        "--html",
        help="Generate a simple HTML table to visualize saved data.",
        action="store_true",
    )
    backup.add_argument(
        "--only-update-accounts",
        help="Only updated information of saved accounts and skip anything else.",
        action="store_true",
    )
    backup.add_argument(
        "-u",
        "--update",
        help="Update existing database if any.",
        action="store_true",
    )

    # restore

    _add_parser(subparsers, "restore", "Restore saved followings, notes and user lists.")

    # wipe

    wipe = _add_parser(subparsers, "wipe", "Wipe all comments, followings, likes, notes and user lists.", FileType.NONE)
    wipe.add_argument(
        "-s",
        "--silent",
        help="Do not show a warning message.",
        action="store_true",
    )

    # info

    info = _add_parser(subparsers, "info", "Get information about account.", FileType.NONE)
    info.add_argument(
        "id",
        type=str,
        help="A numerical ID or a username.",
    )
    info.add_argument(
        "--raw",
        help="Get an output from fansly.com as-is.",
        action="store_true",
    )

    # html

    _add_parser(subparsers, "html", "Generate a simple HTML table to visualize saved data.")

    return parser
