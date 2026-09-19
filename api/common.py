from datetime import date, datetime
from decimal import Decimal
from typing import Any


def json_safe(value: Any):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (datetime, date, Decimal)):
        return value.isoformat() if not isinstance(value, Decimal) else float(value)
    return value


def row_dict(row):
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: json_safe(row[key]) for key in row.keys()}
    if isinstance(row, dict):
        return json_safe(dict(row))
    return json_safe(row)


def rows_dict(rows):
    return [row_dict(row) for row in rows]
