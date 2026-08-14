from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Iterable, TypeVar

from sqlalchemy import DateTime, String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.schemas import (
    Asset,
    AuditEvent,
    IncidentRecord,
    InventoryItem,
    ProductionOrder,
    TechnicianProfile,
)

T = TypeVar("T")


class Base(DeclarativeBase):
    pass


class RecordRow(Base):
    __tablename__ = "forgeguard_records"

    kind: Mapped[str] = mapped_column(String(48), primary_key=True)
    record_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


_MODEL_KIND = {
    Asset: "asset",
    IncidentRecord: "incident",
    InventoryItem: "inventory",
    ProductionOrder: "production",
    TechnicianProfile: "technician",
    AuditEvent: "audit",
}

_KIND_MODEL = {value: key for key, value in _MODEL_KIND.items()}


class PersistentStore:
    """Cross-platform SQLAlchemy store.

    SQLite is the default for desktop, Arch/Debian and Jetson. The same schema
    works with PostgreSQL when FORGEGUARD_DATABASE_URL uses a psycopg URL.
    Records are stored as validated JSON documents so domain contracts stay
    portable while the platform evolves.
    """

    def __init__(self, database_url: str, project_root: Path) -> None:
        self._lock = RLock()
        self.database_url = self._resolve_url(database_url, project_root)
        engine_kwargs: dict[str, object] = {"future": True, "pool_pre_ping": True}
        if self.database_url == "sqlite:///:memory:":
            engine_kwargs.update(
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        elif self.database_url.startswith("sqlite:///"):
            engine_kwargs.update(connect_args={"check_same_thread": False})
        self.engine = create_engine(self.database_url, **engine_kwargs)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)

    @staticmethod
    def _resolve_url(database_url: str, project_root: Path) -> str:
        if not database_url.startswith("sqlite:///") or database_url == "sqlite:///:memory:":
            return database_url
        raw = database_url.removeprefix("sqlite:///")
        path = Path(raw)
        if not path.is_absolute():
            path = project_root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"

    def reset(self) -> None:
        with self._lock, self.Session.begin() as session:
            session.execute(delete(RecordRow))

    def _save(self, model) -> object:
        kind = _MODEL_KIND[type(model)]
        payload = model.model_dump_json()
        now = datetime.now(timezone.utc)
        with self._lock, self.Session.begin() as session:
            row = session.get(RecordRow, {"kind": kind, "record_id": model.id})
            if row is None:
                row = RecordRow(
                    kind=kind,
                    record_id=model.id,
                    payload=payload,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.payload = payload
                row.updated_at = now
        return deepcopy(model)

    def _get(self, model_type: type[T], record_id: str) -> T | None:
        kind = _MODEL_KIND[model_type]
        with self._lock, self.Session() as session:
            row = session.get(RecordRow, {"kind": kind, "record_id": record_id})
            if row is None:
                return None
            return model_type.model_validate_json(row.payload)

    def _list(self, model_type: type[T]) -> list[T]:
        kind = _MODEL_KIND[model_type]
        with self._lock, self.Session() as session:
            rows = session.scalars(
                select(RecordRow).where(RecordRow.kind == kind).order_by(RecordRow.updated_at.desc())
            ).all()
            return [model_type.model_validate_json(row.payload) for row in rows]

    def upsert_asset(self, asset: Asset) -> Asset:
        return self._save(asset)  # type: ignore[return-value]

    def get_asset(self, asset_id: str) -> Asset | None:
        return self._get(Asset, asset_id)

    def list_assets(self) -> list[Asset]:
        return self._list(Asset)

    def save_incident(self, incident: IncidentRecord) -> IncidentRecord:
        return self._save(incident)  # type: ignore[return-value]

    def get_incident(self, incident_id: str) -> IncidentRecord | None:
        return self._get(IncidentRecord, incident_id)

    def list_incidents(self) -> list[IncidentRecord]:
        return sorted(self._list(IncidentRecord), key=lambda item: item.created_at, reverse=True)

    def upsert_inventory(self, item: InventoryItem) -> InventoryItem:
        return self._save(item)  # type: ignore[return-value]

    def list_inventory(self) -> list[InventoryItem]:
        return self._list(InventoryItem)

    def upsert_production(self, order: ProductionOrder) -> ProductionOrder:
        return self._save(order)  # type: ignore[return-value]

    def list_production(self) -> list[ProductionOrder]:
        return self._list(ProductionOrder)

    def upsert_technician(self, technician: TechnicianProfile) -> TechnicianProfile:
        return self._save(technician)  # type: ignore[return-value]

    def list_technicians(self) -> list[TechnicianProfile]:
        return self._list(TechnicianProfile)

    def append_audit(self, event: AuditEvent) -> AuditEvent:
        return self._save(event)  # type: ignore[return-value]

    def list_audit(self, limit: int = 100) -> list[AuditEvent]:
        return self._list(AuditEvent)[:limit]


class InMemoryStore:
    """Dependency-free deterministic store used by unit tests and recovery mode."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, dict[str, object]] = {kind: {} for kind in _KIND_MODEL}

    def reset(self) -> None:
        with self._lock:
            for bucket in self._records.values():
                bucket.clear()

    def _save(self, model):
        kind = _MODEL_KIND[type(model)]
        with self._lock:
            self._records[kind][model.id] = deepcopy(model)
        return deepcopy(model)

    def _get(self, model_type: type[T], record_id: str) -> T | None:
        kind = _MODEL_KIND[model_type]
        with self._lock:
            item = self._records[kind].get(record_id)
            return deepcopy(item) if item is not None else None  # type: ignore[return-value]

    def _list(self, model_type: type[T]) -> list[T]:
        kind = _MODEL_KIND[model_type]
        with self._lock:
            return [deepcopy(item) for item in self._records[kind].values()]  # type: ignore[list-item]

    upsert_asset = lambda self, item: self._save(item)
    get_asset = lambda self, record_id: self._get(Asset, record_id)
    list_assets = lambda self: self._list(Asset)
    save_incident = lambda self, item: self._save(item)
    get_incident = lambda self, record_id: self._get(IncidentRecord, record_id)
    list_incidents = lambda self: sorted(self._list(IncidentRecord), key=lambda item: item.created_at, reverse=True)
    upsert_inventory = lambda self, item: self._save(item)
    list_inventory = lambda self: self._list(InventoryItem)
    upsert_production = lambda self, item: self._save(item)
    list_production = lambda self: self._list(ProductionOrder)
    upsert_technician = lambda self, item: self._save(item)
    list_technicians = lambda self: self._list(TechnicianProfile)
    append_audit = lambda self, item: self._save(item)
    list_audit = lambda self, limit=100: self._list(AuditEvent)[:limit]
