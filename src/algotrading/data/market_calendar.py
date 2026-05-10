from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import importlib

import pandas as pd


US_EQUITY_CALENDAR = "us_equities"
CRYPTO_24_7_CALENDAR = "crypto_24_7"
GENERIC_BUSINESS_CALENDAR = "generic_business"


@dataclass(frozen=True)
class CalendarSchedule:
    calendar_key: str
    provider: str
    precision: str
    dates: pd.DatetimeIndex
    early_closes: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class CalendarDiagnostic:
    calendar_key: str
    provider: str
    precision: str
    expected_count: int
    missing_dates: tuple[str, ...]
    unexpected_dates: tuple[str, ...]
    early_closes: tuple[str, ...]
    note: str


def calendar_key_for_asset(asset_type: str, symbol: str | None = None) -> str:
    if symbol:
        key = calendar_key_for_symbol(symbol)
        if key:
            return key
    if asset_type == "crypto":
        return CRYPTO_24_7_CALENDAR
    if asset_type == "traditional":
        return US_EQUITY_CALENDAR
    if asset_type == "futures":
        return GENERIC_BUSINESS_CALENDAR
    return GENERIC_BUSINESS_CALENDAR


def calendar_key_for_symbol(symbol: str | None) -> str | None:
    value = (symbol or "").upper()
    if not value:
        return None
    if value.endswith("-USD") or value.endswith("USDT") or value in {"BTC", "ETH", "SOL", "ADA"}:
        return CRYPTO_24_7_CALENDAR
    suffix_map = {
        ".L": "XLON",
        ".TO": "XTSE",
        ".V": "XTSX",
        ".PA": "XPAR",
        ".DE": "XETR",
        ".SW": "XSWX",
        ".HK": "XHKG",
        ".T": "XTKS",
        ".AX": "XASX",
    }
    for suffix, calendar in suffix_map.items():
        if value.endswith(suffix):
            return calendar
    return US_EQUITY_CALENDAR


def diagnose_calendar_gaps(
    dates: pd.Series,
    *,
    asset_type: str,
    interval: str,
    symbol: str | None = None,
    calendar_key: str | None = None,
) -> CalendarDiagnostic:
    clean = pd.to_datetime(dates, errors="coerce").dropna().dt.normalize().drop_duplicates().sort_values()
    selected_calendar = calendar_key or calendar_key_for_asset(asset_type, symbol)
    if len(clean) < 2 or interval.lower() != "1d":
        return CalendarDiagnostic(
            calendar_key=selected_calendar,
            provider="not_applied",
            precision="not_applied",
            expected_count=int(len(clean)),
            missing_dates=(),
            unexpected_dates=(),
            early_closes=(),
            note="Calendario detallado solo se aplica a datos diarios.",
        )

    start = clean.iloc[0]
    end = clean.iloc[-1]
    schedule = expected_market_schedule(start, end, calendar_key=selected_calendar)
    observed = pd.DatetimeIndex(clean)
    missing = schedule.dates.difference(observed)
    unexpected = observed.difference(schedule.dates)
    return CalendarDiagnostic(
        calendar_key=schedule.calendar_key,
        provider=schedule.provider,
        precision=schedule.precision,
        expected_count=int(len(schedule.dates)),
        missing_dates=tuple(_format_dates(missing)),
        unexpected_dates=tuple(_format_dates(unexpected)),
        early_closes=schedule.early_closes,
        note=schedule.note,
    )


def expected_trading_dates(
    start: pd.Timestamp | str,
    end: pd.Timestamp | str,
    *,
    calendar_key: str,
) -> pd.DatetimeIndex:
    return expected_market_schedule(start, end, calendar_key=calendar_key).dates


def expected_market_schedule(
    start: pd.Timestamp | str,
    end: pd.Timestamp | str,
    *,
    calendar_key: str,
    prefer_precise: bool = True,
) -> CalendarSchedule:
    start_ts = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end).normalize()
    if end_ts < start_ts:
        return CalendarSchedule(
            calendar_key=calendar_key,
            provider="none",
            precision="none",
            dates=pd.DatetimeIndex([]),
            early_closes=(),
            note="Rango de fechas vacio.",
        )
    if calendar_key == CRYPTO_24_7_CALENDAR:
        return CalendarSchedule(
            calendar_key=calendar_key,
            provider="built_in",
            precision="exact_for_24_7",
            dates=pd.date_range(start_ts, end_ts, freq="D"),
            early_closes=(),
            note=_calendar_note(calendar_key, "built_in"),
        )

    if prefer_precise:
        precise = _precise_market_calendar_schedule(start_ts, end_ts, calendar_key)
        if precise is not None:
            return precise

    return _built_in_market_schedule(start_ts, end_ts, calendar_key)


def _built_in_market_schedule(
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    calendar_key: str,
) -> CalendarSchedule:
    if calendar_key == US_EQUITY_CALENDAR:
        business_days = pd.date_range(start_ts, end_ts, freq="B")
        holidays = pd.DatetimeIndex(
            pd.Timestamp(day)
            for day in us_equity_holidays(start_ts.year, end_ts.year)
        )
        dates = business_days.difference(holidays)
        precision = "built_in_major_holidays"
    else:
        dates = pd.date_range(start_ts, end_ts, freq="B")
        precision = "generic_business_days"
    return CalendarSchedule(
        calendar_key=calendar_key,
        provider="built_in",
        precision=precision,
        dates=dates,
        early_closes=(),
        note=_calendar_note(calendar_key, "built_in"),
    )


def _precise_market_calendar_schedule(
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    calendar_key: str,
) -> CalendarSchedule | None:
    if calendar_key in {CRYPTO_24_7_CALENDAR, GENERIC_BUSINESS_CALENDAR}:
        return None
    try:
        market_calendars = importlib.import_module("pandas_market_calendars")
    except ImportError:
        return None

    for provider_key in _pandas_market_calendar_candidates(calendar_key):
        try:
            calendar = market_calendars.get_calendar(provider_key)
            schedule = calendar.schedule(
                start_date=start_ts.strftime("%Y-%m-%d"),
                end_date=end_ts.strftime("%Y-%m-%d"),
            )
        except Exception:
            continue
        if schedule.empty:
            continue
        dates = pd.DatetimeIndex(pd.to_datetime(schedule.index, errors="coerce")).tz_localize(None).normalize()
        early_closes = _early_closes(calendar, schedule)
        return CalendarSchedule(
            calendar_key=calendar_key,
            provider=f"pandas-market-calendars:{provider_key}",
            precision="exchange_calendar",
            dates=dates,
            early_closes=early_closes,
            note=_calendar_note(calendar_key, f"pandas-market-calendars:{provider_key}", early_closes=early_closes),
        )
    return None


def _pandas_market_calendar_candidates(calendar_key: str) -> tuple[str, ...]:
    aliases = {
        US_EQUITY_CALENDAR: ("NYSE", "XNYS"),
        "NASDAQ": ("NASDAQ", "XNYS", "NYSE"),
        "XLON": ("XLON", "LSE"),
        "XTSE": ("XTSE", "TSX"),
        "XTSX": ("XTSX",),
        "XPAR": ("XPAR",),
        "XETR": ("XETR",),
        "XSWX": ("XSWX",),
        "XHKG": ("XHKG",),
        "XTKS": ("XTKS", "JPX"),
        "XASX": ("XASX",),
    }
    return aliases.get(calendar_key, (calendar_key,))


def _early_closes(calendar, schedule: pd.DataFrame) -> tuple[str, ...]:
    try:
        early = calendar.early_closes(schedule=schedule)
    except Exception:
        return ()
    if early is None or early.empty:
        return ()
    return tuple(_format_dates(pd.DatetimeIndex(pd.to_datetime(early.index, errors="coerce")).dropna()))


def us_equity_holidays(start_year: int, end_year: int) -> tuple[date, ...]:
    holidays: set[date] = set()
    for year in range(start_year, end_year + 1):
        holidays.add(_observed_fixed(year, 1, 1))
        holidays.add(_nth_weekday(year, 1, 0, 3))  # Martin Luther King Jr. Day
        holidays.add(_nth_weekday(year, 2, 0, 3))  # Washington's Birthday
        holidays.add(_good_friday(year))
        holidays.add(_last_weekday(year, 5, 0))  # Memorial Day
        if year >= 2022:
            holidays.add(_observed_fixed(year, 6, 19))  # Juneteenth
        holidays.add(_observed_fixed(year, 7, 4))
        holidays.add(_nth_weekday(year, 9, 0, 1))  # Labor Day
        holidays.add(_nth_weekday(year, 11, 3, 4))  # Thanksgiving
        holidays.add(_observed_fixed(year, 12, 25))
    return tuple(sorted(day for day in holidays if start_year <= day.year <= end_year))


def _observed_fixed(year: int, month: int, day: int) -> date:
    actual = date(year, month, day)
    if actual.weekday() == 5:
        return actual - timedelta(days=1)
    if actual.weekday() == 6:
        return actual + timedelta(days=1)
    return actual


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current + timedelta(days=7 * (nth - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def _good_friday(year: int) -> date:
    return _easter_sunday(year) - timedelta(days=2)


def _easter_sunday(year: int) -> date:
    # Anonymous Gregorian algorithm.
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _format_dates(values: pd.DatetimeIndex) -> list[str]:
    return [pd.Timestamp(value).strftime("%Y-%m-%d") for value in values]


def _calendar_note(calendar_key: str, provider: str, *, early_closes: tuple[str, ...] = ()) -> str:
    if calendar_key == CRYPTO_24_7_CALENDAR:
        return "Cripto se espera 7 dias por semana."
    if provider.startswith("pandas-market-calendars"):
        close_note = f" Incluye {len(early_closes)} media(s) jornada(s) detectada(s)." if early_closes else ""
        return f"Calendario preciso via {provider}.{close_note}"
    if calendar_key == US_EQUITY_CALENDAR:
        return "Fallback built-in USA equity: dias habiles menos feriados principales; no cubre todos los cierres extraordinarios."
    if calendar_key == GENERIC_BUSINESS_CALENDAR:
        return "Calendario generico de dias habiles; revisa manualmente si el activo usa otro mercado."
    return f"Fallback built-in generico para {calendar_key}; instala el extra de calendarios para mayor precision."
