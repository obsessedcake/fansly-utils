from functools import cache
from itertools import islice
from typing import TYPE_CHECKING, Any, Callable, Iterable, Iterator
import json
import logging

from requests import Session

if TYPE_CHECKING:
    from requests import Response

__all__ = ["FanslyApi", "chunks", "offset"]


DEFAULT_CHUNK_SIZE: int = 25
DEFAULT_LIMIT_VALUE: int = 100


# https://stackoverflow.com/questions/42601812
class _Session(Session):
    def __init__(self, authorization_token: str, user_agent: str) -> None:
        super().__init__()
        self.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://fansly.com/",
            "accept-language": "en-US,en;q=0.9",
            "authorization": authorization_token,
            "User-Agent": user_agent,
        })

        self._logger = logging.getLogger("FanslyAPI")
        self._urls_cache: dict[str, str] = {}

    def request(self, method, url, *args, **kwargs):
        # Some Angular stuff (https://angular.io/guide/service-worker-devops)
        if params := kwargs.get("params"):
            params["ngsw-bypass"] = True
        else:
            kwargs["params"] = {"ngsw-bypass": True}

        # The server side expects a comma separated list.
        for k, v in kwargs["params"].items():
            if isinstance(v, (list, tuple, set)):
                kwargs["params"][k] = ",".join(v)

        # Cache a full version of the url.
        joined_url = self._urls_cache.get(url)
        if not joined_url:
            joined_url = "https://apiv3.fansly.com/api/v1" + url
            self._urls_cache[url] = joined_url

        return super().request(method, joined_url, *args, **kwargs)

    def get_json(self, url: str | bytes, params: dict | None = None) -> list[dict] | dict:
        response = self.get(url, params=params)
        return self._process_response(response)

    def post_json(self, url: str | bytes, json: dict | None = None) -> list[dict] | dict:
        response = self.post(url, json=json)
        return self._process_response(response)

    def _log_response(self, response: "Response", is_error: bool = False) -> None:
        req = response.request
        level = logging.ERROR if is_error else logging.DEBUG

        if req.body:
            self._logger.log(level, "%s %s %s", req.method, req.url, json.dumps(req.body))
        else:
            self._logger.log(level, "%s %s", req.method, req.url)

    def _process_response(self, response: "Response") -> list[dict] | dict:
        try:
            response.raise_for_status()
            if self._logger.level == logging.DEBUG:
                self._log_response(response)
        except:
            self._log_response(response, is_error=True)
            self._logger.error("Request has failed with error:", response.json())
            raise

        return response.json()["response"]


# https://stackoverflow.com/questions/312443
def chunks(iterable: Iterable, size: int = DEFAULT_CHUNK_SIZE) -> Iterator[tuple]:
    "chunks('abcdefg', 3) --> ('a','b','c'), ('d','e','f'), ('g',)"
    it = iter(iterable)
    return iter(lambda: tuple(islice(it, size)), ())


def offset(callable: Callable, limit: int = DEFAULT_LIMIT_VALUE) -> Any:
    offset = 0
    while True:
        r = callable(dict(limit=limit, offset=offset))
        if not r:
            break

        yield r
        offset += DEFAULT_LIMIT_VALUE


class FanslyApi:
    def __init__(self, *, authorization_token: str, user_agent: str) -> None:
        self._session = _Session(authorization_token, user_agent)

    @cache
    def accounts(self) -> "_FanslyAccountApi":
        return _FanslyAccountApi(self._session)

    @cache
    def user(self) -> "_FanslyUserApi":
        return _FanslyUserApi(self, self._session)


#
# Fansly - Account API
#


class _FanslyAccountApi:
    def __init__(self, session: _Session):
        self._session = session

    def get(
        self, *, account_id: str | None = None, username: str | None = None, brief: bool = False
    ) -> dict:
        """
        Get account information

        :return:
        """
        if not account_id and not username:
            return {}

        if account_id:
            params = {"accounts_ids": [account_id]}
        else:
            params = {"usernames": [username]}

        response = self.get_batch(**params, brief = brief)
        return response[0] if response else None

    def get_batch(
        self, *, accounts_ids: Iterable[str] | None = None, usernames: Iterable[str] | None = None, brief: bool = True
    ) -> list[dict]:
        """
        Get accounts information in a batch

        :return:
        """
        if not accounts_ids and not usernames:
            return []

        if accounts_ids:
            params = {"ids": accounts_ids}
        else:
            params = {"usernames": usernames}

        response = self._session.get_json("/account", params=params)
        if not response:
            return []

        if not brief:
            return response

        result: list[dict] = []
        for account_info in response:
            notes_info: list[dict] = []
            for note_info in account_info.get("notes", []):
                notes_info.append({
                    "id": note_info["id"],
                    "title": note_info["title"],
                    "data": note_info["note"],
                    "createdAt": note_info["createdAt"],
                    "updatedAt": note_info["updatedAt"],
                })
            result.append({
                "id": account_info["id"],
                "username": account_info["username"],
                "displayName": account_info.get("displayName"),
                "notes": notes_info,
            })
        return result


#
# Fansly - User API
#


class _FanslyUserApi:
    def __init__(self, root_api: FanslyApi, session: _Session):
        self._root_api = root_api
        self._session = session

    @cache
    def id(self) -> str:
        return self._session.get_json("/account/me")["account"]["id"]

    @cache
    def name(self) -> str:
        return self._session.get_json("/account/me")["account"]["username"]

    @cache
    def followers(self) -> "_FanslyUserFollowersApi":
        return _FanslyUserFollowersApi(self._session)

    @cache
    def following(self) -> "_FanslyUserFollowingApi":
        return _FanslyUserFollowingApi(self._root_api, self._session)

    @cache
    def lists(self) -> "_FanslyUserListsApi":
        return _FanslyUserListsApi(self._root_api, self._session)

    @cache
    def media(self) -> "_FanslyUserMediaApi":
        return _FanslyUserMediaApi(self._session)

    @cache
    def notes(self) -> "_FanslyUserNotesApi":
        return _FanslyUserNotesApi(self._root_api, self._session)

    @cache
    def payments(self) -> "_FanslyUserPaymentsApi":
        return _FanslyUserPaymentsApi(self._session)

    @cache
    def subscriptions(self) -> "_FanslyUserSubscriptionsApi":
        return _FanslyUserSubscriptionsApi(self._session)


class _FanslyUserFollowersApi:
    def __init__(self, root_api: FanslyApi, session: _Session) -> None:
        self._root_api = root_api
        self._session = session

    def get_all(self, *, limit: int = DEFAULT_LIMIT_VALUE, offset: int = 0) -> list[str]:
        user_id = self._root_api.user().id()
        params = {
            "before": 0,
            "after": 0,
            "limit": limit,
            "offset": offset,
            "search": "",
        }
        response = self._session.get_json(f"/account/{user_id}/followers", params=params)
        return [obj["followerId"] for obj in response]


class _FanslyUserFollowingApi:
    def __init__(self, root_api: FanslyApi, session: _Session) -> None:
        self._root_api = root_api
        self._session = session

    def get_all(self, *, limit: int = DEFAULT_LIMIT_VALUE, offset: int = 0) -> list[str]:
        user_id = self._root_api.user().id()
        params = {
            "before": 0,
            "after": 0,
            "limit": limit,
            "offset": offset,
        }
        response = self._session.get_json(f"/account/{user_id}/following", params=params)
        return [obj["accountId"] for obj in response]

    def follow(self, account_id: str):
        self._session.post_json(f"/account/{account_id}/followers")

    def unfollow(self, account_id: str):
        self._session.post_json(f"/account/{account_id}/followers/remove")


class _FanslyUserListsApi:
    def __init__(self, root_api: FanslyApi, session: _Session) -> None:
        self._root_api = root_api
        self._session = session

    def get_all(self, *, only_ids: bool = True) -> list[dict] | list[str]:
        """
        Get all user lists

        **UI path:** Account -> Lists.
        """

        response = self._session.get_json("/lists/account", params={"itemId": ""})

        if only_ids:
            return [obj["id"] for obj in response]

        result: list[dict] = []
        for list_info in response:
            result.append({
                "id": list_info["id"],
                "label": list_info["label"],
            })
        return result

    def add_list(self, label: str, description: str = "") -> str:
        data = {
            "label": label,
            "description": description
        }
        self._session.post_json("/lists", json=data)["id"]

    def delete_list(self, list_id: str | None = None) -> None:
        self._session.post_json("/lists/remove", json={"listId": list_id})

    def get_list_items(self, list_id: str) -> list[str]:
        """
        Get all items of a specific list

        **UI path:** Account -> Lists -> <List Name>.
        """

        response =  self._session.get_json("/lists/items", params={"listId": list_id})
        return [obj["id"] for obj in response]

    def add_list_item(self, *, list_id: str, account_id: str) -> None:
        data = {
            "listCommands": [
                {
                    "listItem": {
                        "id": account_id,
                        "listId": list_id,
                    },
                    "type": 1,
                },
            ],
        }
        self._session.post_json("/lists/commands", json=data)

    def add_list_items(self, *, list_id: str, accounts_ids: Iterable[str]) -> None:
        if not accounts_ids:
            return

        commands: list[dict] = []
        for account_id in accounts_ids:
            commands.append({
                "listItem": {
                    "id": account_id,
                    "listId": list_id,
                },
                "type": 1,
            })

        self._session.post_json("/lists/commands", json={"listCommands": commands})

    def delete_list_item(self, *, list_id: str, account_id: str) -> None:
        """
        Get all items of a specific list

        **UI path:** Account -> Lists -> <List Name> -> <Item Name> -> Remove Button.
        """
        self.delete_list_items(list_id=list_id, account_id=[account_id])

    def delete_list_items(self, *, list_id: str, accounts_ids: Iterable[str]) -> None:
        """
        Get all items of a specific list

        **UI path:** Account -> Lists -> <List Name> -> <Item Name> -> Remove Button.
        """
        if not accounts_ids:
            return

        data = {
            "listId": list_id,
            "listItemIds": accounts_ids
        }
        self._session.post_json("/lists/items/remove", json=data)


class _FanslyUserMediaApi:
    def __init__(self, session: _Session) -> None:
        self._session = session

    def purchases(self) -> "_FanslyUserMediaPurchasesApi":
        return _FanslyUserMediaPurchasesApi()


class _FanslyUserMediaPurchasesApi:
    def __init__(self, session: _Session) -> None:
        self._session = session

    def get_all_accounts(self) -> list[str]:
        response = self._session.get("/uservault/albumsnew", params={"accountId": ""})
        aggregation_data = response["aggregationData"]["accountMedia"]

        for data in aggregation_data:
            pass  # TODO

        return []  # TODO


class _FanslyUserNotesApi:
    def __init__(self, root_api: FanslyApi, session: _Session) -> None:
        self._root_api = root_api
        self._session = session

    def get_all(self, account_id: str, *, only_ids: bool = True) -> list[dict] | None:
        account_info = self._root_api.accounts().get(account_id)
        if not account_info:
            return None

        notes_info = account_info.get("notes")
        if not notes_info:
            return None

        if only_ids:
            return [note_info["id"] for note_info in notes_info]

        return notes_info

    def add(self, *, account_id: str, title: str, data: str) -> str:
        data = {
            "contentId": account_id,
            "contentType": 12000,
            "title": title,
            "data": data,
        }
        self._session.post_json("/notes", json=data)["id"]

    def delete(self, *, account_id: str, note_id: str) -> None:
        data = {
            # "accountId": user_account_id,
            "contentId": account_id,
            "contentType": 12000,
            # "title": "test",
            # "note": "test",
            "id": note_id,
        }
        self._session.post_json("/notes/delete", json=data)

class _FanslyUserPaymentsApi:
    def __init__(self, session: _Session) -> None:
        self._session = session

    def get_all(self, *, limit: int = DEFAULT_LIMIT_VALUE, offset: int = 0) -> list[dict]:
        params = {
            "before": 0,
            "after": 0,
            "limit": limit,
            "offset": offset,
        }
        response = self._session.get_json("/account/wallets/transactions", params=params)

        result: list[dict] = []
        for obj in response:
            product_order = obj.get("productOrder")
            if not product_order:  # it's a balance purchase
                continue

            items = product_order["items"]

            metadata = items.get("metadata")
            if not metadata:  # it's a tip
                account_id = items["productId"]
            else:  # it's a paid something
                account_id = json.loads(metadata)["accountId"]

            result.append({
                "id": account_id,
                "createdAt": items["createdAt"],  # unix timestamp in milliseconds
                "price": items["productPrice"],  # price is multiplied by 1000,
                "transactionId": obj["transactionId"],
            })

        return result


# TODO(obsessedcake): I don't have subs right now so I don't know what API endpoints are called
class _FanslyUserSubscriptionsApi:
    def __init__(self, session: _Session) -> None:
        self._session = session

    def get_all(self, *, only_ids: bool = True) -> list[dict] | list[str]:
        return []  # TODO

    def unsubscribe(self, *, account_id: str) -> None:
        pass  # TODO
