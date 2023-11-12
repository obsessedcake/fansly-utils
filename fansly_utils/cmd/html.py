from typing import TYPE_CHECKING

from jinja2 import Environment, PackageLoader, select_autoescape
from sqlalchemy.orm import joinedload, load_only
from sqlalchemy.sql import select

from ..models import Account, List

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session

__all__ = ["generate_html"]


def _collect(session: "Session") -> None:
    accounts = session.scalars(
        select(Account)
        .options(joinedload(Account.lists, innerjoin=True).options(load_only(List.label)))
        .options(joinedload(Account.names, innerjoin=True))
        .options(joinedload(Account.notes, innerjoin=True))
    ).all()
    labels = session.scalars(select(List.label)).all()

    def _contains(account: Account, label: str) -> bool:
        r = next(filter(lambda l: l.label == label, account.lists), None)
        return r is not None

    rows = []
    for account in accounts:
        row = [account.followed]
        for label in labels:
            row.append(_contains(account.lists, label))

        rows.append(
            {
                "id": account.id,
                "username": account_info["username"],
                "deleted": account.deleted,
                "data": row,
                "notes": account.notes,
                "oldNames": account_info["oldNames"],
            }
        )

    return dict(labels=["Following", *labels], rows=rows)


def _render(html_template: str, data: dict, output: "Path") -> None:
    env = Environment(
        autoescape=select_autoescape(), loader=PackageLoader(__package__.split(".")[0])
    )
    template = env.get_template(html_template)
    template.stream(**data).dump(str(output))


def generate_html(db_file: "Path", session: "Session") -> None:
    data = _collect(session)
    output = db_file.with_suffix(".html")

    _render("table.html", data, output)
