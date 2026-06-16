from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    ForeignKey,
    Index,
    func,
    ForeignKeyConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    servers: Mapped[List["Server"]] = relationship(back_populates="client")


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # Platform ID
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_source: Mapped[str] = mapped_column(String(50), default="discord")
    first_scan: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_scan: Mapped[Optional[datetime]] = mapped_column(DateTime)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="servers")
    channels: Mapped[List["Channel"]] = relationship(back_populates="server")


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # Platform ID
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), primary_key=True)
    server_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[Optional[str]] = mapped_column(Text)
    first_scan: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_scan: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_message_ts: Mapped[Optional[datetime]] = mapped_column(DateTime)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    server: Mapped["Server"] = relationship(back_populates="channels")

    __table_args__ = (
        ForeignKeyConstraint(
            ["server_id", "client_id"], ["servers.id", "servers.client_id"]
        ),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # Platform ID
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), primary_key=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    username: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(100), default="unknown")
    messages: Mapped[int] = mapped_column(Integer, default=0)
    reactions_given: Mapped[int] = mapped_column(Integer, default=0)
    reactions_received: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sentiment: Mapped[Optional[str]] = mapped_column(String(50))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    message_id: Mapped[str] = mapped_column(String(100))
    channel_id: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    reply_to: Mapped[Optional[str]] = mapped_column(String(100))
    reactions: Mapped[int] = mapped_column(Integer, default=0)
    export_batch: Mapped[Optional[str]] = mapped_column(String(100))
    platform: Mapped[str] = mapped_column(String(50), default="discord")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["channel_id", "client_id"], ["channels.id", "channels.client_id"]
        ),
        ForeignKeyConstraint(["user_id", "client_id"], ["users.id", "users.client_id"]),
        Index("idx_messages_client_timestamp", "client_id", "timestamp"),
    )


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    server_id: Mapped[Optional[str]] = mapped_column(String(100))
    channel_id: Mapped[Optional[str]] = mapped_column(String(100))
    export_ts: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    messages: Mapped[int] = mapped_column(Integer, default=0)
    new_users: Mapped[int] = mapped_column(Integer, default=0)
    duration_s: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50), default="completed")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["server_id", "client_id"], ["servers.id", "servers.client_id"]
        ),
        ForeignKeyConstraint(
            ["channel_id", "client_id"], ["channels.id", "channels.client_id"]
        ),
    )


class CrossReference(Base):
    __tablename__ = "cross_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    platform1: Mapped[str] = mapped_column(String(50), nullable=False)
    username1: Mapped[str] = mapped_column(String(255), nullable=False)
    platform2: Mapped[str] = mapped_column(String(50), nullable=False)
    username2: Mapped[str] = mapped_column(String(255), nullable=False)
    match_type: Mapped[Optional[str]] = mapped_column(String(50))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(["user_id", "client_id"], ["users.id", "users.client_id"]),
    )


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (Index("idx_topics_client_name", "client_id", "name"),)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_name: Mapped[Optional[str]] = mapped_column(String(255))
    command: Mapped[str] = mapped_column(String(255), nullable=False)
    args_json: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    error_log: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
