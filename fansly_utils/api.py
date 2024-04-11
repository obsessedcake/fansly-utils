import json
import logging
import random
import time
from itertools import islice
from typing import TYPE_CHECKING, Any, Callable, Iterable, Iterator

from requests import Session
from requests.exceptions import HTTPError

if TYPE_CHECKING:
    from logging import Logger

    from requests import Response

__all__ = ["FanslyApi", "chunks", "offset"]


DEFAULT_CHUNK_SIZE: int = 10
DEFAULT_LIMIT_VALUE: int = 25


# https://stackoverflow.com/questions/42601812
class _Session(Session):
    def __init__(self, authorization_token: str, user_agent: str) -> None:
        super().__init__()
        self.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://fansly.com/",
                "accept-language": "en-US,en;q=0.9",
                "authorization": authorization_token,
                "User-Agent": user_agent,
            }
        )

        self._logger = logging.getLogger("FanslyAPI")
        self._urls_cache: dict[str, str] = {}

    @property
    def logger(self) -> "Logger":
        return self._logger

    def invoke_rate_limited(self, callback: Callable) -> Any:
        while True:
            try:
                return callback()
            except HTTPError as e:
                if e.response.status_code != 429:
                    raise

                secs = random.uniform(60, 60 * 4)  # to avoid rate limiter
                self.logger.warning(
                    "Faced rate-limiter! Sleeping for the next %s minutes and %s seconds.",
                    *divmod(round(secs), 60),
                )
                time.sleep(secs)

    def request(self, method, url, *args, **kwargs):
        # Some Angular stuff (https://angular.io/guide/service-worker-devops)
        if params := kwargs.get("params"):
            params["ngsw-bypass"] = True
        else:
            kwargs["params"] = {"ngsw-bypass": True}

        # The server side expects a comma separated list.
        for k, v in kwargs["params"].items():
            if isinstance(v, (list, tuple, set)):
                kwargs["params"][k] = ",".join(map(str, v))

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
        except HTTPError:
            self._log_response(response, is_error=True)
            self._logger.error(
                "Request has failed with %s status: %s", response.status_code, response.text
            )
            raise
        else:
            time.sleep(random.uniform(0.75, 1.25))  # to avoid rate limiter

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

    def accounts(self) -> "_FanslyAccountsApi":
        return _FanslyAccountsApi(self._session)

    def chats(self) -> "_FanslyChatsApi":
        return _FanslyChatsApi(self._session)

    def collections(self) -> "_FanslyCollectionsApi":
        return _FanslyCollectionsApi(self._session)

    def media(self) -> "_FanslyMediaApi":
        return _FanslyMediaApi(self._session)

    def lists(self) -> "_FanslyListsApi":
        return _FanslyListsApi(self, self._session)

    def notes(self) -> "_FanslyNotesApi":
        return _FanslyNotesApi(self, self._session)

    def posts(self) -> "_FanslyPostsApi":
        return _FanslyPostsApi(self._session)

    def user(self) -> "_FanslyUserApi":
        return _FanslyUserApi(self, self._session)

    def sessions(self) -> "_FanslySessionsApi":
        return _FanslySessionsApi(self._session)


#
# Fansly - Account API
#


class _FanslyAccountsApi:
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

        response = self.get_batch(**params, brief=brief)
        return response[0] if response else None

    def _get_batch(
        self,
        accounts_ids: Iterable[str] | None,
        usernames: Iterable[str] | None,
        brief: bool,
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
                notes_info.append(
                    {
                        "id": note_info["id"],
                        "title": note_info["title"],
                        "data": note_info["note"],
                        "createdAt": note_info["createdAt"],
                        "updatedAt": note_info["updatedAt"],
                    }
                )
            result.append(
                {
                    "id": account_info["id"],
                    "username": account_info["username"],
                    "displayName": account_info.get("displayName"),
                    "notes": notes_info,
                }
            )
        return result

    def get_batch(
        self,
        *,
        accounts_ids: Iterable[str] | None = None,
        usernames: Iterable[str] | None = None,
        brief: bool = False,
    ) -> list[dict]:
        return self._session.invoke_rate_limited(
            lambda: self._get_batch(accounts_ids, usernames, brief)
        )


#
# Fansly - Messages API
#


class _FanslyChatsApi:
    def __init__(self, session: _Session):
        self._session = session

    def messages(self) -> "_FanslyChatMessagesApi":
        return _FanslyChatMessagesApi(self._session)

    def get_batch(self, *, limit: int = DEFAULT_LIMIT_VALUE, offset: int = 0) -> list[dict]:
        params = {
            "flags": 0,
            "limit": limit,
            "offset": offset,
            "search": "",
            "sortOrder": 1,  # newest
            "subscriptionTierId": "",  # all
        }

        response = self._session.get_json("/messaging/groups", params=params)

        result: list[dict] = []
        for group_info in response.get("data", []):
            result.append(
                {
                    "id": group_info["groupId"],
                    "partnerAccountId": group_info["partnerAccountId"],
                    "partnerUsername": group_info["partnerUsername"],
                }
            )
        return result


class _FanslyChatMessagesApi:
    def __init__(self, session: _Session):
        self._session = session

    def get_batch(
        self,
        *,
        chat_id: str,
        oldest_msg_id: str = "0",
        limit: int = DEFAULT_LIMIT_VALUE,
        brief: bool = False,
    ) -> list[str]:
        params = {
            "before": oldest_msg_id,
            "groupId": chat_id,
            "limit": limit,
        }

        try:
            response = self._session.get_json("/message", params=params)
        except HTTPError as e:
            if e.response.status_code == 500:  # dead account
                return []

            raise

        messages = response["messages"]

        if not brief:
            messages

        result = []
        for message in messages:
            result.append({"id": message["id"], "senderId": message["senderId"]})

        return result

    def delete(self, *, message_id: str) -> None:
        self._session.post("/message/delete", json={"messageId": message_id})


#
# Fansly - Collections API
#


class _FanslyCollectionsApi:
    def __init__(self, session: _Session):
        self._session = session

    def items(self) -> "_FanslyCollectionItemsApi":
        return _FanslyCollectionItemsApi(self._session)

    def get_all(self, *, brief: bool = False) -> list[dict[str, Any]]:
        response = self._session.get_json("/uservault/albumsnew")

        if not brief:
            return response

        result: list[dict[str, Any]] = []
        for obj in response["albums"]:
            result.append({"id": obj["id"], "title": obj["title"], "type": obj["type"]})

        return result

    def create(self, *, title: str, description: str = "") -> str:
        data = {
            "accountId": None,
            "description": description,
            "id": None,
            "public": 0,
            "thumbnailId": None,
            "title": title,
            "type": 0,
        }
        self._session.post_json("/uservault/albums", json=data)["id"]

    def delete(self, *, collection_id: str) -> None:
        self._session.post("/uservault/album/delete", json={"albumId": collection_id})


class _FanslyCollectionItemsApi:
    def __init__(self, session: _Session):
        self._session = session

    def get_batch(
        self, *, collection_id: str, oldest_id: str = "0", limit: int = DEFAULT_LIMIT_VALUE
    ) -> list[dict[str, Any]]:
        params = {
            "albumId": collection_id,
            "before": oldest_id,
            "after": 0,
            "limit": limit,
        }
        response = self._session.get_json("/uservault/album/content", params=params)

        result: dict[str, dict[str, Any]] = {}
        for obj in response["albumContent"]:
            result[obj["mediaId"]] = {"id": obj["id"]}

        for obj in response["aggregationData"]["accountMedia"]:
            result[obj["mediaId"]]["accountId"] = obj["accountId"]

        return list(result.values())

    def delete(self, *, collection_id: str, items_ids: list[str] | str) -> None:
        data = {
            "albumId": collection_id,
            "albumContentIds": [items_ids] if isinstance(items_ids, str) else items_ids,
        }
        self._session.post("/uservault/album/content/delete", json=data)


#
# Fansly - Lists API
#


class _FanslyListsApi:
    def __init__(self, root_api: FanslyApi, session: _Session) -> None:
        self._root_api = root_api
        self._session = session

    def items(self) -> "_FanslyListItemsApi":
        return _FanslyListItemsApi(self._session)

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
            result.append(
                {
                    "id": list_info["id"],
                    "label": list_info["label"],
                }
            )
        return result

    def create(self, label: str, description: str = "") -> str:
        data = {"label": label, "description": description}
        self._session.post_json("/lists", json=data)["id"]

    def delete(self, list_id: str | None) -> None:
        self._session.post("/lists/remove", json={"listId": list_id})


class _FanslyListItemsApi:
    def __init__(self, session: _Session) -> None:
        self._session = session

    def get_all(self, list_id: str) -> list[str]:
        """
        Get all items of a specific list

        **UI path:** Account -> Lists -> <List Name>.
        """
        response = self._session.get_json("/lists/items", params={"listId": list_id})
        return [obj["id"] for obj in response]

    def add(self, list_id: str, *, accounts_ids: list[str] | str) -> None:
        if not accounts_ids:
            return

        commands: list[dict] = []
        for account_id in [accounts_ids] if isinstance(accounts_ids, str) else accounts_ids:
            commands.append(
                {
                    "listItem": {
                        "id": account_id,
                        "listId": list_id,
                    },
                    "type": 1,
                }
            )

        self._session.post_json("/lists/commands", json={"listCommands": commands})

    def delete(self, list_id: str, *, accounts_ids: list[str] | str) -> None:
        """
        Get all items of a specific list

        **UI path:** Account -> Lists -> <List Name> -> <Item Name> -> Remove Button.
        """
        if not accounts_ids:
            return

        data = {
            "listId": list_id,
            "listItemIds": [accounts_ids] if isinstance(accounts_ids, str) else accounts_ids,
        }
        self._session.post("/lists/items/remove", json=data)


#
# Fansly - Media API
#


class _FanslyMediaApi:
    def __init__(self, session: _Session) -> None:
        self._session = session

    def purchases(self) -> "_FanslyUserMediaPurchasesApi":
        return _FanslyUserMediaPurchasesApi(self._session)


class _FanslyUserMediaPurchasesApi:
    def __init__(self, session: _Session) -> None:
        self._session = session

    def get_all_accounts(self) -> list[str]:
        # response = self._session.get("/uservault/albumsnew", params={"accountId": ""})
        # aggregation_data = response["aggregationData"]["accountMedia"]

        return []  # TODO(obsessedcake): Implement this.


#
# Fansly - Notes API
#


class _FanslyNotesApi:
    def __init__(self, root_api: FanslyApi, session: _Session) -> None:
        self._root_api = root_api
        self._session = session

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
        self._session.post("/notes/delete", json=data)


#
# Fansly - Posts API
#


class _FanslyPostsApi:
    def __init__(self, session: _Session):
        self._session = session

    def get(self, *, post_id: str) -> dict[str, Any] | None:
        response = self._session.get_json("/post", params={"ids": post_id})

        posts = response["posts"]
        if not posts:
            return None

        return posts[0]

    def delete(self, *, post_id: str) -> None:
        self._session.post(f"/post/{post_id}/delete")


#
# Fansly - Sessions API
#


class _FanslySessionsApi:
    def __init__(self, session: _Session):
        self._session = session

    def get_batch(
        self,
        *,
        oldest_session_id: str = "0",
        limit: int = DEFAULT_LIMIT_VALUE,
        only_ids: bool = True,
    ) -> list[str]:
        params = {
            "before": oldest_session_id,
            "limit": limit,
            "status": "0, 2",
        }
        response = self._session.get_json("/sessions", params=params)

        if only_ids:
            return [obj["id"] for obj in response]

        return response

    def close(self, *, session_id: str) -> None:
        self._session.post_json("/session/close", json={"id": session_id})


#
# Fansly - User API
#


class _FanslyUserApi:
    def __init__(self, root_api: FanslyApi, session: _Session):
        self._root_api = root_api
        self._session = session

    def id(self) -> str:
        return self._session.get_json("/account/me")["account"]["id"]

    def name(self) -> str:
        return self._session.get_json("/account/me")["account"]["username"]

    def followers(self) -> "_FanslyUserFollowersApi":
        return _FanslyUserFollowersApi(self._session)

    def following(self) -> "_FanslyUserFollowingApi":
        return _FanslyUserFollowingApi(self._root_api, self._session)

    def payments(self) -> "_FanslyUserPaymentsApi":
        return _FanslyUserPaymentsApi(self._session)

    def subscriptions(self) -> "_FanslyUserSubscriptionsApi":
        return _FanslyUserSubscriptionsApi(self._session)


class _FanslyUserFollowersApi:
    def __init__(self, root_api: FanslyApi, session: _Session) -> None:
        self._root_api = root_api
        self._session = session

    def get_batch(self, *, limit: int = DEFAULT_LIMIT_VALUE, offset: int = 0) -> list[str]:
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

    def get_batch(self, *, limit: int = DEFAULT_LIMIT_VALUE, offset: int = 0) -> list[str]:
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
        self._session.post(f"/account/{account_id}/followers")

    def unfollow(self, account_id: str):
        url = f"/account/{account_id}/followers/remove"
        self._session.invoke_rate_limited(lambda: self._session.post(url))


class _FanslyUserPaymentsApi:
    def __init__(self, session: _Session) -> None:
        self._session = session

    def get_batch(self, *, limit: int = DEFAULT_LIMIT_VALUE, offset: int = 0) -> list[dict]:
        params = {
            "before": 0,
            "after": 0,
            "limit": limit,
            "offset": offset,
        }
        response = self._session.get_json("/account/wallets/transactions", params=params)

        result: list[dict] = []
        for obj in response["data"]:
            transaction_id = obj["transactionId"]
            self._session.logger.debug("Processing payment with %s transaction id", transaction_id)

            product_order = obj.get("productOrder")
            if not product_order:  # it's a balance purchase
                continue

            items = product_order["items"]
            assert len(items) == 1
            items = items[0]

            metadata = items.get("metadata")
            if not metadata:  # it's a tip
                account_id = items["productId"]
            else:  # it's a paid something
                metadata = json.loads(metadata)
                account_id = metadata.get("accountId")
                if not account_id:
                    account_id = metadata["authorId"]  # it's a locked text

            result.append(
                {
                    "accountId": account_id,
                    "createdAt": product_order["createdAt"],  # unix timestamp in milliseconds
                    "price": items["productPrice"],  # price is multiplied by 1000,
                    "transactionId": transaction_id,
                }
            )

        return result


class _FanslyUserSubscriptionsApi:
    def __init__(self, session: _Session) -> None:
        self._session = session

    def get_all(self, *, only_ids: bool = True) -> list[dict] | list[str]:
        response = self._session.get_json("/subscriptions")
        subscriptions = response["subscriptions"]

        if only_ids:
            return [obj["id"] for obj in subscriptions]

        return subscriptions

    # TODO(obsessedcake): I don't have subs right now so I don't know what API endpoints is called
    def unsubscribe(self, *, sub_id: str) -> None:
        pass  # TODO
