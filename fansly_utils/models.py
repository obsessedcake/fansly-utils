from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.engine import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.schema import Column, ForeignKey, Table
from sqlalchemy.types import DateTime, Integer, TypeDecorator

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["Account", "AccountName", "connect", "List", "Note", "Payment"]


class Base(DeclarativeBase):
    pass


a2l = Table(
    "a2l_association",
    Base.metadata,
    Column("aid", ForeignKey("accounts.id"), primary_key=True),
    Column("lid", ForeignKey("lists.id"), primary_key=True),
)


class CommonDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, str):
            value = int(value)

        if isinstance(value, int):
            return datetime.utcfromtimestamp(value)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)

    created_at: Mapped[datetime] = mapped_column(CommonDateTime)

    deleted: Mapped[bool] = mapped_column(default=False, index=True)
    followed: Mapped[bool] = mapped_column(default=False)

    lists: Mapped[list["List"]] = relationship(secondary=a2l, back_populates="accounts")
    names: Mapped[list["AccountName"]] = relationship(back_populates="account")
    notes: Mapped[list["Note"]] = relationship(back_populates="account")
    payments: Mapped[list["Payment"]] = relationship(back_populates="account")


class AccountName(Base):
    __tablename__ = "account_names"

    id: Mapped[int] = mapped_column(primary_key=True)

    created_at: Mapped[datetime] = mapped_column(default=False)
    value: Mapped[str] = mapped_column(index=True, unique=True)

    is_custom_name: Mapped[bool] = mapped_column(default=False)
    is_display_name: Mapped[bool] = mapped_column(default=False)
    is_username: Mapped[bool] = mapped_column(default=False)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    account: Mapped["Account"] = relationship(back_populates="names")


class List(Base):
    __tablename__ = "lists"

    id: Mapped[int] = mapped_column(primary_key=True)

    created_at: Mapped[datetime] = mapped_column(CommonDateTime)
    label: Mapped[str] = mapped_column(index=True, unique=True)

    accounts: Mapped[list["Account"]] = relationship(secondary=a2l, back_populates="lists")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)

    created_at: Mapped[datetime] = mapped_column(CommonDateTime)
    title: Mapped[str]
    data: Mapped[str]

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    account: Mapped["Account"] = relationship(back_populates="notes")


class PaymentDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if isinstance(value, str):
            value = int(value)

        if isinstance(value, int):
            return datetime.utcfromtimestamp(value / 1000)


class PaymentPrice(TypeDecorator):
    impl = Integer
    cache_ok = True

    def process_result_value(self, value: int) -> None:
        return value / 1000


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    created_at: Mapped[datetime] = mapped_column(PaymentDateTime)
    price: Mapped[int] = mapped_column(PaymentPrice)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    account: Mapped["Account"] = relationship(back_populates="payments")


def connect(file: "Path", password: str | None) -> sessionmaker:
    if password:
        engine = create_engine(
            f"sqlite+pysqlcipher://:{password}@/{file}?cipher=aes-256-cfb&kdf_iter=64000"
        )
    else:
        engine = create_engine(f"sqlite:///{file}")

    if not file.exists():
        Base.metadata.create_all(engine)

    return sessionmaker(engine)
