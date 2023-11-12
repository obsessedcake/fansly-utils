from typing import TYPE_CHECKING

from sqlalchemy.sql import and_, not_, select

from ..api import chunks
from ..models import Account
from .utils import contains, extract_ids

if TYPE_CHECKING:
    from logging import Logger

    from sqlalchemy.orm import Session

    from ..api import FanslyApi

__all__ = ["restore"]


def restore(api: "FanslyApi", logger: "Logger", session: "Session") -> None:
    logger.info("Re-following all previously followed accounts...")

    following = session.scalars(
        select(Account.id).where(and_(Account.followed, not_(Account.deleted)))
    ).all()
    for account_id in following:
        api.user().following().follow(account_id)

    logger.info("Recreating all user lists...")

    for list_info in data["lists"]:
        list_label = list_info["label"]

        logger.info("Recreating '%s' user list...", list_label)
        list_id = api.user().lists().add_list(list_label)

        logger.debug("Removing dead accounts from '%s' list...", list_label)
        list_items = list(filter(list_info["items"], lambda lid: lid not in data["deleted"]))

        logger.debug("Adding %s account(s) to '%s' user list...", len(list_items), list_label)
        api.user().lists().add_list_items(list_id=list_id, account_ids=list_items)

    logger.debug("Removing dead accounts...")
    accounts = list(filter(lambda a: not contains(data["deleted"], a["id"]), data["accounts"]))

    logger.info("Recreating all user notes...")

    for account in accounts:
        notes = account.get("notes")
        if not notes:
            continue

        logger.info("Adding %s note(s) to '%s' account...", len(notes), account["username"])
        api.user().notes().add(account_id=account["id"], title=notes["title"], data=notes["data"])

    logger.info("Checking accounts...")

    for chunk in chunks(accounts):
        response = api.accounts().get_batch(accounts_ids=extract_ids(chunk))
        for account in chunk:
            account_id = account["id"]
            if account_id not in response:
                logger.warning("'%s' has deleted their account!", account["username"])
                continue

            old_name = account["username"]
            new_name = response[account_id]["username"]
            if old_name != new_name:
                logger.warning("'%s' has changed their name to '%s'!", old_name, new_name)
