from typing import TYPE_CHECKING

from jinja2 import Environment, PackageLoader, select_autoescape

from .utils import contains, load_backup

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["generate_html"]


def _render(html_template: str, data: dict, output: "Path") -> None:
    env = Environment(
        autoescape=select_autoescape(),
        loader=PackageLoader(__package__.split(".")[0])
    )
    template = env.get_template(html_template)
    template.stream(**data).dump(str(output))


def _generate_html_table(db_file: "Path", data: dict) -> None:
    data["accounts"].sort(key=lambda o: o["username"])

    rows = []
    for account_info in data["accounts"]:
        account_id = account_info["id"]

        row = [contains(data["following"], account_id)]
        for list_info in data["lists"]:
            row.append(contains(list_info["items"], account_id))

        rows.append({
            "id": account_id,
            "username": account_info["username"],
            "deleted": contains(data["deleted"], account_id),
            "data": row,
            "notes": account_info["notes"],
            "oldNames": account_info["oldNames"],
        })

    labels = ["Following"]
    for list_info in data["lists"]:
        labels.append(list_info["label"])

    _render(
        "table.html",
        data=dict(labels=labels, rows=rows),
        output=db_file.with_suffix(".html")
    )


def _generate_html_charts(db_file: "Path", data: dict) -> None:
    pass  # TODO(obsessedcake): Implement this function.


def generate_html(db_file: "Path") -> None:
    data = load_backup(db_file)

    for func in (_generate_html_table, _generate_html_charts):
        func(db_file, data)
