import random
import shutil
import time
from typing import TYPE_CHECKING

from requests.exceptions import HTTPError

from ..api import chunks, offset
from .utils import contains, extract_ids, find_by, load_backup, merge_lists, save_backup

if TYPE_CHECKING:
    from logging import Logger
    from pathlib import Path

    from ..api import FanslyApi

__all__ = ["backup", "update_accounts"]


def backup(api: "FanslyApi", logger: "Logger", db_file: "Path", update: bool) -> None:
    accounts_ids: set[str] = set()
    accounts: list[dict] = []
    deleted: list[str] = []
    following: list[str] = []
    lists: list[dict] = []
    payments: list[dict] = []

    # collect

    logger.info("Backup all user lists...")

    for list_info in api.user().lists().get_all(only_ids=False):
        logger.info("Backup '%s' user list", list_info["label"])

        items = api.user().lists().get_list_items(list_info["id"])
        accounts_ids |= set(items)

        list_info["items"] = items
        lists.append(list_info)

    logger.info("Processed %s lists!", len(lists))
    logger.info("Backup a list of accounts that the user follows...")

    for ids in offset(lambda kwarg: api.user().following().get_all(**kwarg)):
        following.extend(ids)
        accounts_ids |= set(ids)

    logger.info("Found %s accounts that the user follows!", len(following))
    logger.info("Backup all available accounts info...")

    time.sleep(random.uniform(5, 15))  # to avoid rate limiter

    for chunk in chunks(accounts_ids):
        response = api.accounts().get_batch(accounts_ids=chunk)
        for account_id in chunk:
            account_info = find_by(response, key="id", value=account_id)
            if account_info:
                accounts.append(account_info)
                continue

            logger.warning(
                "Detected dead or unavailable in your region account with '%s' id!",
                account_id,
            )
            deleted.append(account_id)

    for account in accounts:
        account["oldNames"] = []  # to simplify logic, let's inject this now.

    logger.info("Backup all available payments...")
    for payments_chunk in offset(lambda kwarg: api.user().payments().get_all(**kwarg)):
        payments.extend(payments_chunk)
        accounts_ids |= set(extract_ids(payments_chunk, key="accountId"))

    logger.info("Found %s payments!", len(following))

    # update data

    if update and db_file.exists():
        logger.debug("Loading old database...")
        old_data = load_backup(db_file)

        db_file_backup = db_file.with_suffix("bak")
        if not db_file_backup.exists():
            logger.debug("Backup '%s' file to '%s'", db_file, db_file_backup)
            shutil.copy2(str(db_file), str(db_file_backup))

        logger.debug("Merging accounts...")
        for old_account_info in old_data["accounts"]:
            account_info = find_by(accounts, key="id", value=old_account_info["id"])
            if not account_info:
                logger.debug("Adding '%s' account", old_account_info["username"])
                accounts.append(old_account_info)
                continue

            old_name = old_account_info["username"]
            new_name = account_info["username"]

            if old_name != new_name:
                logger.warning("'%s' has changed their name to '%s'", old_name, new_name)
                account_info["oldNames"].append(old_name)

        logger.debug("Merging deleted accounts...")
        deleted = old_data["deleted"]

        logger.debug("Merging followings...")
        following = merge_lists(following, old_data["following"])

        logger.debug("Merging lists...")
        for old_list_info in old_data["lists"]:
            old_list_label = old_list_info["label"]
            list_info = find_by(lists, key="label", value=old_list_label)
            if not list_info:
                logger.debug("Adding '%s' list", old_list_label)
                lists.append(old_list_info)
            else:
                logger.debug("Updating '%s' list", old_list_label)
                list_info["items"] = merge_lists(list_info["items"], old_list_info["items"])

        logger.debug("Merging payments...")
        for old_payment_info in old_data["payments"]:
            old_tid = old_payment_info["transactionId"]
            payment_info = find_by(lists, key="transactionId", value=old_tid)
            if not payment_info:
                logger.debug("Adding payment with '%s' transaction id", old_list_label)
                lists.append(old_payment_info)

    # dump

    backup_data = {
        "accounts": accounts,
        "deleted": deleted,
        "following": following,
        "lists": lists,
        "payments": payments,
    }

    logger.info("Dumping all found data to the '%s' file...", db_file)
    save_backup(db_file, backup_data)


def update_accounts(api: "FanslyApi", logger: "Logger", db_file: "Path") -> None:
    logger.info("Loading saved data from '%s' file...", db_file)
    data = load_backup(db_file)

    logger.info("Checking accounts...")

    logger.debug("Removing dead accounts...")
    accounts = list(filter(lambda a: not contains(data["deleted"], a["id"]), data["accounts"]))

    for chunk in chunks(accounts):
        response = api.accounts().get_batch(accounts_ids=extract_ids(chunk))
        for old_account_info in chunk:
            old_id = old_account_info["id"]
            old_name = old_account_info["username"]

            account_info = find_by(response, key="id", value=old_id)
            if not account_info:
                logger.warning(
                    "'%s' has deleted their account or disabled it for your region", old_name
                )
                data["deleted"].append(old_id)
                continue

            new_name = account_info["username"]
            if old_name != new_name:
                logger.warning("'%s' has changed their name to '%s'", old_name, new_name)
                old_account_info["username"] = new_name
                old_account_info["oldNames"].append(old_name)

    logger.info("Dumping updated data back to the '%s' file...", db_file)
    save_backup(db_file, data)
