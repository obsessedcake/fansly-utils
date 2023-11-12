import logging
import sys
from configparser import ConfigParser
from typing import TYPE_CHECKING

from requests.exceptions import HTTPError
from rich.logging import RichHandler

from .api import FanslyApi
from .cli import get_cli_arg_parser
from .cmd import (
    PaymentsProcessor,
    backup,
    generate_html,
    get_account_info,
    process_payments,
    restore,
    update_accounts,
    wipe,
)
from .models import connect

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
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
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
        if args.command == "info":
            get_account_info(api, args.id, args.raw)
            return

        if args.command == "wipe":
            wipe(api, logger, args.silent)
            return

        password = config["db"].get("password")
        with connect(args.file, password) as session:
            if args.command == "backup":
                if not args.only_update_accounts:
                    backup(api, logger, session, args.update)

                if args.update:
                    update_accounts(api, logger, session)

                if args.html:
                    generate_html(args.file, session)
            elif args.command == "restore":
                restore(api, logger, session)
            elif args.command == "html":
                generate_html(args.file, session)
            elif args.command == "payments":
                if args.by_accounts:
                    process_payments(session, PaymentsProcessor.BY_ACCOUNTS)
                elif args.by_years:
                    process_payments(session, PaymentsProcessor.BY_YEARS)
                elif args.total:
                    process_payments(session, PaymentsProcessor.TOTAL)
    except HTTPError:
        pass  # NOTE(obsessedcake): Should be already logged on FanslyApi side.
    except Exception:
        logger.exception("")


if __name__ == "__main__":
    main()
