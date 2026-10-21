"""Каталог заведения: мастера, услуги, график. Загружается из JSON-пресета."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
# id попадают в callback_data (лимит Telegram — 64 байта), поэтому держим их короткими
_ID_RE = re.compile(r"^[a-z0-9_]{1,12}$")


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class Service:
    id: str
    title: str
    duration: int  # минуты
    price: int


@dataclass(frozen=True)
class Master:
    id: str
    name: str
    about: str
    service_ids: tuple[str, ...]
    schedule: dict[int, tuple[time, time]]  # weekday (0=пн) -> (начало, конец)
    breaks: tuple[tuple[time, time], ...] = ()

    def hours_on(self, day: date) -> tuple[time, time] | None:
        return self.schedule.get(day.weekday())


@dataclass(frozen=True)
class Business:
    id: str
    name: str
    emoji: str
    description: str
    address: str
    phone: str
    currency: str
    slot_step: int
    services: dict[str, Service] = field(default_factory=dict)
    masters: dict[str, Master] = field(default_factory=dict)

    @property
    def title(self) -> str:
        return f"{self.emoji} {self.name}".strip()

    def services_of(self, master_id: str) -> list[Service]:
        return [self.services[s] for s in self.masters[master_id].service_ids]

    def format_price(self, price: int) -> str:
        if price == 0:
            return "бесплатно"
        return f"{price:,}".replace(",", " ") + f" {self.currency}"


def _parse_time(value: str, where: str) -> time:
    try:
        return time.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise CatalogError(f"{where}: неверное время {value!r}, нужен формат ЧЧ:ММ") from exc


def _check_id(value: str, where: str) -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise CatalogError(f"{where}: id {value!r} должен состоять из a-z, 0-9, _ и быть не длиннее 12 символов")
    return value


def parse_business(raw: dict) -> Business:
    biz_id = _check_id(raw.get("id", ""), "business")
    services: dict[str, Service] = {}
    for s in raw.get("services", []):
        sid = _check_id(s.get("id"), f"{biz_id}.services")
        if s["duration"] <= 0:
            raise CatalogError(f"{biz_id}.{sid}: длительность должна быть больше нуля")
        services[sid] = Service(sid, s["title"], int(s["duration"]), int(s.get("price", 0)))

    masters: dict[str, Master] = {}
    for m in raw.get("masters", []):
        mid = _check_id(m.get("id"), f"{biz_id}.masters")
        where = f"{biz_id}.{mid}"
        unknown = [s for s in m.get("services", []) if s not in services]
        if unknown:
            raise CatalogError(f"{where}: неизвестные услуги {unknown}")
        schedule: dict[int, tuple[time, time]] = {}
        for day_name, (start, end) in m.get("schedule", {}).items():
            if day_name not in WEEKDAYS:
                raise CatalogError(f"{where}: неизвестный день {day_name!r}, используйте {WEEKDAYS}")
            t_start, t_end = _parse_time(start, where), _parse_time(end, where)
            if t_start >= t_end:
                raise CatalogError(f"{where}: в {day_name} начало смены позже конца")
            schedule[WEEKDAYS.index(day_name)] = (t_start, t_end)
        breaks = tuple((_parse_time(a, where), _parse_time(b, where)) for a, b in m.get("breaks", []))
        masters[mid] = Master(mid, m["name"], m.get("about", ""), tuple(m.get("services", [])), schedule, breaks)

    if not services or not masters:
        raise CatalogError(f"{biz_id}: нужен хотя бы один мастер и одна услуга")

    return Business(
        id=biz_id,
        name=raw["name"],
        emoji=raw.get("emoji", ""),
        description=raw.get("description", ""),
        address=raw.get("address", ""),
        phone=raw.get("phone", ""),
        currency=raw.get("currency", "₽"),
        slot_step=int(raw.get("slot_step_minutes", 30)),
        services=services,
        masters=masters,
    )


def load_businesses(presets_dir: Path, ids: tuple[str, ...]) -> dict[str, Business]:
    result: dict[str, Business] = {}
    for preset_id in ids:
        path = presets_dir / f"{preset_id}.json"
        if not path.exists():
            raise CatalogError(f"Пресет не найден: {path}")
        business = parse_business(json.loads(path.read_text(encoding="utf-8")))
        result[business.id] = business
    return result
