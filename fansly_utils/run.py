from configparser import ConfigParser
from typing import TYPE_CHECKING
import logging
import sys

from requests.exceptions import HTTPError
from rich.logging import RichHandler

from .api import FanslyApi
from .cli import get_cli_arg_parser
from .cmd import *

if TYPE_CHECKING:
    from argparse import Namespace


def _setup_logging(args: "Namespace") -> None:
    if args.warnings:
        log_level = logging.WARNING
    else:
        log_level = args.log_level

    logging.basicConfig(
        level=log_level,
        format="[%(name)s] %(message)s",
        datefmt="%X",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)]
    )


def main() -> None:
    try:
        args = get_cli_arg_parser().parse_args()
    except FileNotFoundError as e:
        print(f"File not found: {str(e)}!")
        sys.exit(1)

    _setup_logging(args)

    config = ConfigParser()
    config.read(args.config)

    api = FanslyApi(
        authorization_token=config["user"]["authorization_token"],
        user_agent=config["user"]["user_agent"],
    )
    logger = logging.getLogger(__package__.replace("_", "-"))

    try:
        if args.command == "backup":
            if not args.only_update_accounts:
                update_accounts(api, logger, args.file)
            else:
                backup(api, logger, args.file, args.update)

            if args.html:
                generate_html(args.file)
        elif args.command == "restore":
            restore(api, logger, args.file)
        elif args.command == "wipe":
            wipe(api, logger, args.file, args.silent)
        elif args.command == "html":
            generate_html(args.file)
        elif args.command == "info":
            get_account_info(api, args.id, args.raw)
    except HTTPError:
        pass  # NOTE(obsessedcake): Should be already logged on FanslyApi side.
    except Exception:
        logger.exception("")

if __name__ == "__main__":
    main()
