"""Number/date -> display strings (API_CONTRACT §2). None in -> "Data not available" out."""
from datetime import date

MISSING = "Data not available"


def _money(v, body):
    return f"-${body}" if v < 0 else f"${body}"


def money_large(v):
    if v is None:
        return None
    a = abs(v)
    for limit, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if a >= limit:
            return _money(v, f"{a / limit:.2f}{suffix}")
    return _money(v, f"{a:,.2f}")


def money_per_share(v):
    return None if v is None else _money(v, f"{abs(v):.2f}")


def pct_change(v):
    return None if v is None else f"{v:+.1f}%"


def pct_level(v):
    return None if v is None else f"{v:.2f}%"


def date_display(iso):
    if not iso:
        return None
    d = date.fromisoformat(iso[:10])
    return f"{d:%b} {d.day}, {d.year}"


def field(value, fn):
    return {"value": value, "display": (fn(value) if value is not None else None) or MISSING}
