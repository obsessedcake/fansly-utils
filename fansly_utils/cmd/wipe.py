from typing import TYPE_CHECKING

from ..api import chunks, offset
from .utils import extract_ids

if TYPE_CHECKING:
    from logging import Logger

    from ..api import FanslyApi

__all__ = ["wipe"]

_WIPE_WARNING = """The following content will be completely removed from your account:"
- all active subscriptions,
- all users who you are following,
- all custom lists,
- all notes,
- all likes.
Are you sure? [y/N]
"""


def wipe(api: "FanslyApi", logger: "Logger", no_warning: bool) -> None:
    if not no_warning:
        answer = input(_WIPE_WARNING)
        if (not answer) or (answer.lower() in ("n", "no")):
            return

    logger.info("Unsubscribing from all user's active subscriptions...")
    logger.warning("Unsubscribing is not implemented! Skipping this action!")
    # TODO(obsessedcake): Check comments in API implementation.
    for sub_info in api.user().subscriptions().get_all(only_ids=False):
        logger.info("Unsubscribing from %s...", sub_info["username"])
        api.user().subscriptions().unsubscribe(sub_id=sub_info["id"])

    logger.info("Wiping all user's lists...")
    accounts_ids = set()

    for list_info in api.user().lists().get_all(only_ids=False):
        logger.info("Wiping '%s' user's list", list_info["label"])

        list_id = list_info["id"]
        list_items = api.user().lists().get_list_items(list_id)

        accounts_ids |= set(list_items)

        api.user().lists().delete_list_items(list_id=list_id, accounts_ids=list_items)
        api.user().lists().delete_list(list_id=list_id)

    logger.info("Unfollowing all accounts that the user follows...")

    for ids in offset(lambda kwarg: api.user().following().get_all(**kwarg)):
        for account_id in ids:
            api.user().following().unfollow(account_id)
        accounts_ids |= set(ids)

    logger.info("Wipe all available notes...")

    for chunk in chunks(accounts_ids):
        for account in api.accounts().get_batch(accounts_ids=extract_ids(chunk)):
            notes = account.get("notes")
            if not notes:
                continue

            logger.debug(
                "Wiping %s note(s) from '%s' account...",
                len(notes),
                account["username"],
            )
            for note in notes:
                api.user().notes().delete(
                    account_id=account["id"],
                    note_id=note["id"],
                )

    logger.info("Removing likes from all posts...")
    logger.warning("Removing likes from all posts is not implemented! Skipping this action!")
    # TODO(obsessedcake): Implement this.

    logger.info("Removing all collections...")
    logger.warning("Removing all collections is not implemented! Skipping this action!")
    # TODO(obsessedcake): Implement this.

    logger.info("Removing all your messages...")
    logger.warning("Removing all your messages is not implemented! Skipping this action!")
    # TODO(obsessedcake): Implement this.

    logger.info("Removing all your comments to posts...")
    logger.warning("Removing all your comments to posts is not implemented! Skipping this action!")
    # TODO(obsessedcake): Implement this.
