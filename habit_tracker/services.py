from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta

from .db import get_db

DEFAULT_CATEGORY_COLOR = "#465fff"

def parse_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)

def parse_month(value: str | None) -> date:
    if value:
        return date.fromisoformat(f"{value}-01")
    today = date.today()
    return today.replace(day=1)

def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)

def pretty_date(value: date) -> str:
    return value.strftime("%b %d, %Y")

def percentage(completed: int, expected: int) -> int:
    if expected <= 0:
        return 0
    return round((completed / expected) * 100)

def _optional_int(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    return int(text)

def _month_end(month_start: date) -> date:
    return month_start.replace(day=monthrange(month_start.year, month_start.month)[1])

def _calendar_bounds(month_start: date):
    month_end = _month_end(month_start)
    calendar_start = month_start - timedelta(days=month_start.weekday())
    calendar_end = month_end + timedelta(days=(6 - month_end.weekday()))
    return calendar_start, calendar_end, month_end

def list_categories():
    connection = get_db()
    rows = connection.execute(
        """
        SELECT id, name, color, created_at
        FROM categories
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()

    categories = []
    for row in rows:
        categories.append(
            {
                "id": row["id"],
                "name": row["name"],
                "color": row["color"] or DEFAULT_CATEGORY_COLOR,
                "created_at": row["created_at"],
            }
        )
    return categories

def get_category(category_id: int | None):
    if not category_id:
        return None
    connection = get_db()
    row = connection.execute(
        """
        SELECT id, name, color, created_at
        FROM categories
        WHERE id = ?
        """,
        (category_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "color": row["color"] or DEFAULT_CATEGORY_COLOR,
        "created_at": row["created_at"],
    }

def save_category(category_id, name: str, color: str):
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Category name is required.")

    category_identifier = _optional_int(category_id)
    chosen_color = (color or DEFAULT_CATEGORY_COLOR).strip()
    connection = get_db()

    duplicate = connection.execute(
        """
        SELECT id
        FROM categories
        WHERE lower(name) = lower(?)
          AND (? IS NULL OR id != ?)
        """,
        (clean_name, category_identifier, category_identifier),
    ).fetchone()
    if duplicate:
        raise ValueError("That category already exists.")

    if category_identifier:
        connection.execute(
            """
            UPDATE categories
            SET name = ?, color = ?
            WHERE id = ?
            """,
            (clean_name, chosen_color, category_identifier),
        )
    else:
        connection.execute(
            """
            INSERT INTO categories (name, parent_id, color)
            VALUES (?, NULL, ?)
            """,
            (clean_name, chosen_color),
        )
    connection.commit()

def delete_category(category_id):
    category_identifier = _optional_int(category_id)
    if category_identifier is None:
        raise ValueError("Category not found.")

    connection = get_db()
    category = connection.execute(
        """
        SELECT id, name
        FROM categories
        WHERE id = ?
        """,
        (category_identifier,),
    ).fetchone()
    if category is None:
        raise ValueError("Category not found.")

    log_count = connection.execute(
        """
        SELECT COUNT(*) AS total
        FROM logs
        WHERE category_id = ?
        """,
        (category_identifier,),
    ).fetchone()["total"]

    connection.execute(
        """
        DELETE FROM categories
        WHERE id = ?
        """,
        (category_identifier,),
    )
    connection.commit()
    return {"name": category["name"], "log_count": log_count}

def save_daily_logs(log_date: str | date, form):
    parsed_date = parse_date(log_date)
    connection = get_db()
    
    # Delete all logs for this date first
    connection.execute("DELETE FROM logs WHERE log_date = ?", (parsed_date.isoformat(),))
    
    # Track the categories that were checked off on this date
    category_ids = set()
    for key in form.keys():
        if key.startswith("completed_"):
            cat_id = key.split("_")[1]
            if form.get(key) == "on":
                category_ids.add(int(cat_id))

    for cat_id in category_ids:
        connection.execute(
            "INSERT INTO logs (category_id, log_date, completed) VALUES (?, ?, 1)",
            (cat_id, parsed_date.isoformat(),)
        )
    
    connection.execute("CREATE TABLE IF NOT EXISTS day_status (log_date TEXT PRIMARY KEY, status_color TEXT)")
    day_status_color = form.get("status_color", "none")
    if day_status_color in ["green", "yellow", "red"]:
        connection.execute(
            "INSERT INTO day_status (log_date, status_color) VALUES (?, ?) ON CONFLICT(log_date) DO UPDATE SET status_color=excluded.status_color",
            (parsed_date.isoformat(), day_status_color)
        )
    else:
        connection.execute("DELETE FROM day_status WHERE log_date = ?", (parsed_date.isoformat(),))
    
    connection.commit()

def _fetch_logs_by_category(category_ids: list[int], start_date: date, end_date: date):
    if not category_ids:
        return {}

    connection = get_db()
    placeholders = ", ".join("?" for _ in category_ids)
    rows = connection.execute(
        f"""
        SELECT category_id, log_date
        FROM logs
        WHERE category_id IN ({placeholders}) AND log_date BETWEEN ? AND ? AND completed = 1
        """,
        (*category_ids, start_date.isoformat(), end_date.isoformat()),
    ).fetchall()

    grouped = defaultdict(dict)
    for row in rows:
        grouped[row["category_id"]][parse_date(row["log_date"])] = True
    return grouped

def _build_calendar(month_start: date, selected_date: date, categories: list[dict], logs_by_category: dict, day_statuses: dict):
    calendar_start, calendar_end, month_end = _calendar_bounds(month_start)
    today = date.today()
    weeks = []
    week = []

    for current_date in daterange(calendar_start, calendar_end):
        completed = 0
        categories_done = []

        for category in categories:
            if logs_by_category.get(category["id"], {}).get(current_date):
                completed += 1
                categories_done.append({
                    "name": category["name"],
                    "color": category["color"],
                })

        if current_date > today:
            tone = "future"
        elif completed > 0:
            tone = "strong"
        else:
            tone = "idle"

        week.append(
            {
                "date": current_date,
                "day": current_date.day,
                "is_current_month": current_date.month == month_start.month,
                "is_today": current_date == today,
                "is_selected": current_date == selected_date,
                "completed": completed,
                "expected": len(categories),
                "tone": tone,
                "dots": categories_done,
                "completed_category_ids": [cat["id"] for cat in categories if logs_by_category.get(cat["id"], {}).get(current_date)],
                "status_color": day_statuses.get(current_date, 'none'),
            }
        )

        if len(week) == 7:
            weeks.append(week)
            week = []

    return {
        "weeks": weeks,
        "month_label": month_start.strftime("%B %Y"),
        "month_value": month_start.strftime("%Y-%m"),
        "previous_month": (month_start - timedelta(days=1)).strftime("%Y-%m"),
        "next_month": (month_end + timedelta(days=1)).strftime("%Y-%m"),
    }

def seed_demo_data():
    connection = get_db()
    existing = connection.execute("SELECT COUNT(*) AS total FROM categories").fetchone()
    if existing["total"]:
        return

    categories = [
        ("Study", "#ec4899"),
        ("Work", "#465fff"),
        ("Exercise", "#12b76a"),
    ]

    for name, color in categories:
        connection.execute(
            """
            INSERT INTO categories (name, parent_id, color)
            VALUES (?, NULL, ?)
            """,
            (name, color),
        )
    connection.commit()

def get_dashboard_data(selected_date=None, selected_month=None, edit_category_id=None):
    month_start = parse_month(selected_month)
    today = date.today()
    month_end = _month_end(month_start)

    if selected_date:
        log_date = parse_date(selected_date)
    elif today.year == month_start.year and today.month == month_start.month:
        log_date = today
    else:
        log_date = month_start

    if log_date < month_start:
        log_date = month_start
    if log_date > month_end:
        log_date = month_end

    categories = list_categories()
    
    calendar_start, calendar_end, _ = _calendar_bounds(month_start)
    
    connection = get_db()
    connection.execute("CREATE TABLE IF NOT EXISTS day_status (log_date TEXT PRIMARY KEY, status_color TEXT)")
    status_rows = connection.execute(
        "SELECT log_date, status_color FROM day_status WHERE log_date BETWEEN ? AND ?",
        (calendar_start.isoformat(), calendar_end.isoformat())
    ).fetchall()
    day_statuses = {parse_date(row["log_date"]): row["status_color"] for row in status_rows}
    
    logs_by_category = _fetch_logs_by_category([cat["id"] for cat in categories], calendar_start, calendar_end)
    
    calendar = _build_calendar(month_start, log_date, categories, logs_by_category, day_statuses)

    category_stats = []
    for category in categories:
        month_completed = 0
        cat_logs = logs_by_category.get(category["id"], {})
        for current_date in daterange(month_start, min(month_end, today)):
            if cat_logs.get(current_date):
                month_completed += 1
                
        category_stats.append({
            "id": category["id"],
            "name": category["name"],
            "color": category["color"],
            "completed": month_completed,
            "expected": (min(month_end, today) - month_start).days + 1
        })

    edit_category = get_category(_optional_int(edit_category_id))
    category_form = edit_category or {"id": "", "name": "", "color": "#465fff"}

    # Attach log status for the specifically selected date
    for cat in categories:
        cat["is_completed"] = bool(logs_by_category.get(cat["id"], {}).get(log_date))

    return {
        "month": calendar,
        "selected_date": log_date,
        "selected_date_label": pretty_date(log_date),
        "categories": categories,
        "category_stats": category_stats,
        "manage": {
            "category_form": category_form,
        },
        "today_iso": today.isoformat(),
        "is_backfill": log_date != today,
    }
