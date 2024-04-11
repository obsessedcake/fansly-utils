from typing import TYPE_CHECKING

from ..api import chunks, offset
from .utils import extract_ids

if TYPE_CHECKING:
    from logging import Logger
    from pathlib import Path

    from ..api import FanslyApi

__all__ = ["wipe"]

_WIPE_WARNING = """The following content will be completely removed from your account:"
- all active subscriptions;
- all creators you are following;
- all lists;
- all notes,
- all likes;
- all posts.
Are you sure? [y/N]
"""


def _inspect_payments(api: "FanslyApi", logger: "Logger") -> set[str]:
    logger.info("Inspecting all user's payments")
    accounts_ids: set[str] = set()

    for payments_chunk in offset(lambda kwarg: api.user().payments().get_batch(**kwarg)):
        accounts_ids |= set(extract_ids(payments_chunk, key="accountId"))

    return accounts_ids


def _wipe_user_lists(api: "FanslyApi", logger: "Logger") -> set[str]:
    logger.info("Wiping all user's lists")
    accounts_ids: set[str] = set()

    for list_info in api.lists().get_all(only_ids=False):
        logger.info("Wiping '%s' user's list", list_info["label"])

        list_id = list_info["id"]
        list_items = api.lists().items().get_all(list_id)

        accounts_ids |= set(list_items)

        api.lists().items().delete(list_id, accounts_ids=list_items)
        api.lists().delete(list_id)

    return accounts_ids


def _wipe_user_collections(api: "FanslyApi", logger: "Logger") -> set[str]:
    logger.info("Wiping all user's collections")
    accounts_ids: set[str] = set()

    for collection in api.collections().get_all(brief=True):
        collection_id = collection["id"]
        collection_type = collection["type"]

        if collection_type == 2007:  # purchases
            continue

        logger.info("Wiping %r user's collections", collection["title"])

        while True:
            items = api.collections().items().get_batch(collection_id=collection_id)
            if not items:
                break

            items_ids: list[str] = []
            for item in items:
                accounts_ids.add(item["accountId"])
                items_ids.append(item["id"])

            api.collections().items().delete(collection_id=collection_id, items_ids=items_ids)

        if not collection_type:  # user's collections
            api.collections().delete(collection_id=collection_id)

    return accounts_ids


def _wipe_user_comments(api: "FanslyApi", logger: "Logger") -> None:
    logger.info("Removing all user's comments")
    accounts_ids: set[str] = set()

    self_id = api.user().id()
    params = {
        "before": "0",
        "after": 0,
        "type": [1002, 1004, 1005, 2002, 5003],  # likes, post replies, post quotes
    }

    while True:
        response = api._session.get_json("/notifications", params=params)

        notifications = response["notifications"]
        if not notifications:
            break

        params["before"] = notifications[-1]

        for post in response["posts"]:
            post_account_id = post["accountId"]

            if post_account_id != self_id:
                accounts_ids.add(post_account_id)
                continue

            post_id = post["id"]
            if api.posts().get(post_id=post_id):  # let's skip already deleted posts.
                api.posts().delete(post_id=post_id)

    return accounts_ids


def _wipe_user_messages(api: "FanslyApi", logger: "Logger") -> None:
    logger.info("Removing all user's messages")
    accounts_ids: set[str] = set()

    for chats in offset(lambda kwarg: api.chats().get_batch(**kwarg)):
        for chat in chats:
            partner_id = chat["partnerAccountId"]
            accounts_ids.add(partner_id)

            logger.info("Inspecting chat with %r", chat["partnerUsername"])

            oldest_msg_id = "0"
            while True:
                messages = (
                    api.chats()
                    .messages()
                    .get_batch(chat_id=chat["id"], oldest_msg_id=oldest_msg_id, brief=True)
                )
                if not messages:
                    break

                for message in messages:
                    if message["senderId"] != partner_id:
                        api.chats().messages().delete(message_id=message["id"])

                oldest_msg_id = message["id"]

    return accounts_ids


def _unfollow(api: "FanslyApi", logger: "Logger") -> set[str]:
    logger.info("Unfollowing all accounts that the user follows")
    accounts_ids: set[str] = set()

    while True:
        followings = api.user().following().get_batch()
        if not followings:
            break

        for account_id in followings:
            api.user().following().unfollow(account_id)
            accounts_ids.add(account_id)

    return accounts_ids


def _wipe_user_notes(api: "FanslyApi", logger: "Logger", accounts_ids: set[str]) -> None:
    logger.info("Wipe all available user's notes")

    for chunk in chunks(accounts_ids):
        for account in api.accounts().get_batch(accounts_ids=chunk):
            notes = account.get("notes")
            if not notes:
                continue

            logger.info(
                "Wiping %s note(s) from '%s' account",
                len(notes),
                account["username"],
            )
            for note in notes:
                api.notes().delete(account_id=account["id"], note_id=note["id"])


def _wipe_subscriptions(api: "FanslyApi", logger: "Logger") -> None:
    logger.info("Unsubscribing from all user's active subscriptions")
    logger.warning("Unsubscribing is not implemented! Skipping this action!")

    # TODO(obsessedcake): Check comments in API implementation.
    for sub_id in api.user().subscriptions().get_all():
        api.user().subscriptions().unsubscribe(sub_id=sub_id)


def _wipe_sessions(api: "FanslyApi", logger: "Logger") -> None:
    logger.info("Removing all user's web sessions")

    while True:
        sessions = api.sessions().get_batch()
        sessions.pop(0)  # don't close current session

        if not sessions:
            break

        for session_id in sessions:
            api.sessions().close(session_id=session_id)


def wipe(api: "FanslyApi", logger: "Logger", backup_path: "Path", no_warning: bool) -> None:
    if not no_warning:
        answer = input(_WIPE_WARNING)
        if (not answer) or (answer.lower() in ("n", "no")):
            return

    accounts_ids: set[str] = set()
    if backup_path.exists():
        with backup_path.open("r", encoding="utf-8") as file:
            for line in file:
                accounts_ids.add(line.rstrip())

    try:
        for wipe in (
            _inspect_payments,
            _wipe_user_lists,
            _wipe_user_collections,
            _wipe_user_comments,
            _wipe_user_messages,
            _unfollow,
        ):
            accounts_ids |= wipe(api, logger)

        _wipe_user_notes(api, logger, accounts_ids)
    finally:
        with backup_path.open("w", encoding="utf-8") as file:
            for account_id in accounts_ids:
                file.write(account_id)
                file.write("\n")

    _wipe_subscriptions(api, logger)
    _wipe_sessions(api, logger)
