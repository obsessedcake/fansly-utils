from datetime import datetime
from enum import IntEnum, auto
from typing import TYPE_CHECKING

import inflect
from dateutil.relativedelta import relativedelta
from rich import print

from .utils import find_by, load_backup

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["process_payments", "PaymentsProcessor"]

#
# Utils
#


def _convert_ts(timestamp: int) -> datetime:
    return datetime.utcfromtimestamp(timestamp / 1000)


_LANG = inflect.engine()


# https://gist.github.com/thatalextaylor/7408395
def _pretty_timedelta(delta: relativedelta) -> str:
    years = delta.years
    months = delta.months

    if not years and not months:
        return None

    measures = ((years, "year"), (months, "month"))
    return _LANG.join(
        [f"{count} {_LANG.plural(noun, count)}" for (count, noun) in measures if count]
    )


#
# Processors
#


def _calculate_total_spending(data: dict) -> None:
    payments = data["payments"]

    first_payment = _convert_ts(payments[0]["createdAt"])
    total = sum(payment["price"] for payment in payments) / 1000

    delta = relativedelta(datetime.today(), first_payment)
    delta = _pretty_timedelta(delta)

    if delta:
        print(
            f"You have spent {total}$ in total during {delta} "
            f"since your first payment at {first_payment:%Y %b %d}!"
        )
    else:
        print(
            f"You have spent {total}$ in total since your first payment at "
            "{first_payment:%Y-%m-%d}!"
        )


def _distribute_by_accounts(data: dict) -> None:
    result: list[dict] = []
    for payment in data["payments"]:
        entry = find_by(result, key="accountId", value=payment["accountId"])
        if entry:
            entry["price"] += payment["price"]
        else:
            result.append({"accountId": payment["accountId"], "price": payment["price"]})

    result.sort(key=lambda e: e["price"])

    for entry in result:
        account_info = find_by(data["accounts"], key="id", value=entry["accountId"])
        if account_info:
            entry["accountId"] = account_info["username"]

    for entry in result:
        print(f'{entry["accountId"]}: {entry["price"] / 1000}$')


def _distribute_by_years(data: dict) -> None:
    result: list[dict] = []
    for payment in data["payments"]:
        year = _convert_ts(payment["createdAt"]).year
        entry = find_by(result, key="year", value=year)
        if entry:
            entry["price"] += payment["price"]
        else:
            result.append({"year": year, "price": payment["price"]})

    result.sort(key=lambda e: e["year"])

    for entry in result:
        print(f'{entry["year"]}: {entry["price"] / 1000}$')


#
# Facade
#


class PaymentsProcessor(IntEnum):
    BY_ACCOUNTS = auto()
    BY_YEARS = auto()
    TOTAL = auto()


_PROCESSORS = {
    PaymentsProcessor.BY_ACCOUNTS: _distribute_by_accounts,
    PaymentsProcessor.BY_YEARS: _distribute_by_years,
    PaymentsProcessor.TOTAL: _calculate_total_spending,
}


def process_payments(db_file: "Path", processor: PaymentsProcessor) -> None:
    data = load_backup(db_file)
    if not data["payments"]:
        print("No payments found!")
        return

    _PROCESSORS[processor](data)
