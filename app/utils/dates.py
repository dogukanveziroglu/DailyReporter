from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Union
from zoneinfo import ZoneInfo

TZ_TR = ZoneInfo("Europe/Istanbul")

def now_tr() -> datetime:
    return datetime.now(TZ_TR)

def today_tr() -> date:
    return now_tr().date()

def fmt_hm_tr(dt: datetime) -> str:
    """Verilen datetime'ı TR saatine çevirip HH:MM döner."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_TR)
    return dt.astimezone(TZ_TR).strftime("%H:%M")

def parse_iso_dt(value: str) -> datetime:
    """ISO string'i datetime'a çevirir, TZ yoksa Europe/Istanbul varsayar."""
    if not value:
        return now_tr()
    s = value.strip()
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # 'Z' ile biten değerleri +00:00'a çevir
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_TR)
    return dt

def is_future(d: Union[date, datetime]) -> bool:
    """Verilen tarih/zaman gelecekte mi? (TR saatine göre)"""
    if isinstance(d, datetime):
        dt = d if d.tzinfo else d.replace(tzinfo=TZ_TR)
        return dt.astimezone(TZ_TR) > now_tr()
    return d > today_tr()

def daterange_days(days_back: int) -> tuple[date, date]:
    """Bugün ve geriye doğru N gün (1 -> sadece bugün)."""
    end = today_tr()
    start = end - timedelta(days=max(0, days_back - 1))
    return start, end
