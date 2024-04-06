import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from logging import Logger
    from pathlib import Path

    from ..api import FanslyApi

__all__ = ["add_list_items"]


@dataclass
class Creators:
    dead_ids: set[str] = field(default_factory=set)
    ids: dict[str, tuple[str, str]] = field(default_factory=dict)

    dead_usernames: set[str] = field(default_factory=set)
    username2id: dict[str, str] = field(default_factory=dict)


def _read_file(file: "Path", creators: Creators) -> tuple[set[str], set[str], set[str]]:
    ids: set[str] = set()
    usernames: set[str] = set()

    found_ids: set[str] = set()

    for id_or_username in file.open("r", encoding="utf-8").readlines():
        id_or_username = id_or_username.rstrip().removeprefix("@")

        if id_or_username.isdigit():
            if id_or_username in creators.dead_ids:
                pass
            elif id_or_username in creators.ids:
                found_ids.add(id_or_username)
            else:
                ids.add(id_or_username)
        elif id_or_username != "unknown":
            if id_or_username in creators.dead_usernames:
                pass
            elif account_id := creators.username2id.get(id_or_username):
                found_ids.add(account_id)
            else:
                usernames.add(id_or_username)

    return ids, usernames, found_ids


def _get_creators_ids(api: "FanslyApi", ids: set[str], usernames: set[str]) -> list[dict[str, Any]]:
    found_creators_info = api.accounts().get_batch(accounts_ids=ids, brief=True)
    found_creators_info += api.accounts().get_batch(usernames=usernames, brief=True)

    return found_creators_info


def _collect_names(data: list[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for found_account_info in data:
        result.add(found_account_info["displayName"])
        result.add(found_account_info["username"])
    return result


def _log_ids(logger: "Logger", creators: Creators, accounts_ids: Iterable[str], text: str) -> None:
    for account_id in accounts_ids:
        username, display_name = creators.ids.get(account_id)
        if display_name:
            logger.info("%r (%r) %s!", display_name, username, text)
        else:
            logger.info("%r %s!", username, text)


def _add_list_items(api: "FanslyApi", logger: "Logger", file: "Path", creators: Creators) -> None:
    logger.info("Processing %r file!", file.name)

    # read file

    provided_ids, provided_usernames, found_ids = _read_file(file, creators)

    # get creators ids

    found_info = _get_creators_ids(api, provided_ids, provided_usernames)
    for found_account_info in found_info:
        found_account_id = found_account_info["id"]
        found_display_name = found_account_info["displayName"]
        found_username = found_account_info["username"]

        creators.ids[found_account_id] = (found_username, found_display_name)

        creators.username2id[found_display_name] = found_account_id
        creators.username2id[found_username] = found_account_id

        found_ids.add(found_account_id)

    # log missing creators

    dead_ids = provided_ids - found_ids
    creators.dead_ids |= dead_ids

    for dead_id in sorted(dead_ids):
        logger.warning("%r id is dead or unavailable in your region!", dead_id)

    dead_usernames = provided_usernames - _collect_names(found_info)
    creators.dead_usernames |= dead_usernames

    for dead_usernames in sorted(dead_usernames):
        logger.warning("%r is dead or unavailable in your region!", dead_usernames)

    # get or create user list

    list_id: str = ""

    label = file.stem.lower()
    for list_info in api.user().lists().get_all(only_ids=False):
        if list_info["label"].lower() == label:
            logger.info("Found %r in user lists!", label)

            list_id = list_info["id"]
            list_items = set(api.user().lists().get_list_items(list_info["id"]))

            _log_ids(logger, creators, found_ids & list_items, "is already added")

            found_ids -= set(list_items)
            break
    else:
        logger.warning("Couldn't find %r in user lists! Creating one", label)
        list_id = api.user().lists().add_list(label)

    # get or create user list

    api.user().lists().add_list_items(list_id=list_id, accounts_ids=found_ids)
    _log_ids(logger, creators, found_ids, "has been successfully added")

    time.sleep(random.uniform(15, 60))  # to avoid rate limiter


def add_list_items(api: "FanslyApi", logger: "Logger", files: list["Path"]) -> None:
    creators = Creators()

    for file in sorted(set(files)):
        _add_list_items(api, logger, file, creators)
