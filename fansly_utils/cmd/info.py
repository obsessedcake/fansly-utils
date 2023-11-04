import json
from typing import TYPE_CHECKING

from rich import print

if TYPE_CHECKING:
    from ..api import FanslyApi

__all__ = ["get_account_info"]


def get_account_info(api: "FanslyApi", id: str, raw: bool) -> None:
    brief = not raw
    if id.isdigit():
        info = api.accounts().get(account_id=id, brief=brief)
    else:
        info = api.accounts().get(username=id, brief=brief)

    print(json.dumps(info, indent=4, sort_keys=True))
