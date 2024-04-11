from typing import TYPE_CHECKING

from ..api import chunks
from .utils import contains, extract_ids, load_backup

if TYPE_CHECKING:
    from logging import Logger
    from pathlib import Path

    from ..api import FanslyApi

__all__ = ["restore"]


def restore(api: "FanslyApi", logger: "Logger", db_file: "Path") -> None:
    logger.info("Loading saved data from '%s' file...", db_file)
    data = load_backup(db_file)

    logger.debug("Removing dead accounts from followings...")
    following = list(filter(lambda aid: not contains(data["deleted"], aid), data["following"]))

    logger.info("Re-following all previously followed accounts...")
    for account_id in following:
        api.user().following().follow(account_id)

    logger.info("Recreating all user lists...")
    for list_info in data["lists"]:
        list_label = list_info["label"]

        logger.info("Recreating '%s' user list...", list_label)
        list_id = api.lists().create(list_label)

        logger.debug("Removing dead accounts from '%s' list...", list_label)
        list_items = list(filter(list_info["items"], lambda lid: lid not in data["deleted"]))

        logger.debug("Adding %s account(s) to '%s' user list...", len(list_items), list_label)
        api.lists().items().add(list_id, account_ids=list_items)

    logger.debug("Removing dead accounts...")
    accounts = list(filter(lambda a: not contains(data["deleted"], a["id"]), data["accounts"]))

    logger.info("Recreating all user notes...")

    for account in accounts:
        notes = account.get("notes")
        if not notes:
            continue

        logger.info("Adding %s note(s) to '%s' account...", len(notes), account["username"])
        api.notes().add(account_id=account["id"], title=notes["title"], data=notes["data"])

    logger.info("Checking accounts...")

    for chunk in chunks(accounts):
        response = api.accounts().get_batch(accounts_ids=extract_ids(chunk), brief=True)
        for account in chunk:
            account_id = account["id"]
            if account_id not in response:
                logger.warning("'%s' has deleted their account!", account["username"])
                continue

            old_name = account["username"]
            new_name = response[account_id]["username"]
            if old_name != new_name:
                logger.warning("'%s' has changed their name to '%s'!", old_name, new_name)
