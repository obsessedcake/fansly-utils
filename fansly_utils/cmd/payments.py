from datetime import datetime
from enum import IntEnum, auto
from typing import TYPE_CHECKING

import inflect
from dateutil.relativedelta import relativedelta
from rich import print
from sqlalchemy.sql import extract, func, select

from ..models import Account, AccountName, Payment

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

__all__ = ["process_payments", "PaymentsProcessor"]


#
# Processors
#


def _calculate_total_spending(session: "Session") -> None:
    first_payment: datetime = session.scalar(select(func.min(Payment.created_at)))
    last_payment: datetime = session.scalar(select(func.max(Payment.created_at)))
    total: float = session.scalar(select(func.sum(Payment.price)))

    # https://gist.github.com/thatalextaylor/7408395
    def _pretty_timedelta(delta: relativedelta) -> str:
        lang = inflect.engine()

        years = delta.years
        months = delta.months

        if not years and not months:
            return None

        measures = ((years, "year"), (months, "month"))
        return lang.join(
            [f"{count} {lang.plural(noun, count)}" for (count, noun) in measures if count]
        )

    delta = relativedelta(last_payment, first_payment)
    delta = _pretty_timedelta(delta)

    date_format = "%b %d %Y"
    first_payment = first_payment.strftime(date_format)
    last_payment = last_payment.strftime(date_format)

    def _(data) -> str:
        return f"[bold red]{data}[/bold red]"

    if delta:
        print(
            f"You have spent {_(total)}$ in total during {_(delta)} in period "
            f"from {_(first_payment)} to {_(last_payment)}!"
        )
    else:
        print(f"You have spent {_(total)}$ in period from {_(first_payment)} to {_(last_payment)}!")


def _distribute_by_accounts(session: "Session") -> None:
    total = func.sum(Payment.price).label("total")
    result = session.scalars(
        select(AccountName.value, total)
        .join_from(Account, AccountName)
        .join(Payment)
        .where(func.max(AccountName.created_at))
        .order_by(total.desc())
    ).all()

    for account_name, total_price in result:
        print(f"{account_name}: {total_price}$")


def _distribute_by_years(session: "Session") -> None:
    year = extract("YEAR", Payment.created_at).label("year")
    total = func.sum(Payment.price).label("total")
    result = session.scalars(select(year, total).order_by(year.desc())).all()

    for year, total_price in result:
        print(f"{year}: {total_price}$")


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


def process_payments(session: "Session", processor: PaymentsProcessor) -> None:
    if not session.scalars(select(Payment)).one_or_none():
        print("No payments found!")
        return

    _PROCESSORS[processor](session)
