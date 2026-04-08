from flask import Blueprint, flash, redirect, render_template, request, url_for

from . import services

bp = Blueprint("main", __name__)

def _redirect_to(endpoint: str, anchor: str | None = None, **params):
    clean_params = {key: value for key, value in params.items() if value not in (None, "", [])}
    target = url_for(endpoint, **clean_params)
    if anchor:
        target = f"{target}#{anchor}"
    return redirect(target)

def _base_payload(selected_date=None, selected_month=None, edit_category_id=None):
    return services.get_dashboard_data(
        selected_date=selected_date,
        selected_month=selected_month,
        edit_category_id=edit_category_id,
    )

def _with_page_meta(payload, *, current_page: str, page_title: str, page_description: str, page_context_label=None, page_context_value=None):
    payload.update(
        {
            "current_page": current_page,
            "page_title": page_title,
            "page_description": page_description,
            "page_context_label": page_context_label,
            "page_context_value": page_context_value,
            "nav_month": payload["month"]["month_value"],
            "nav_date": payload["selected_date"].isoformat(),
        }
    )
    return payload


@bp.get("/")
def dashboard():
    payload = _base_payload(
        selected_date=request.args.get("date"),
        selected_month=request.args.get("month"),
    )
    payload = _with_page_meta(
        payload,
        current_page="dashboard",
        page_title="Dashboard",
        page_description="",
        page_context_label="Current month",
        page_context_value=payload["month"]["month_label"],
    )
    return render_template("dashboard.html", **payload)


@bp.post("/checkin")
def save_checkin():
    log_date = request.form.get("log_date")
    month = request.form.get("return_month")
    services.save_daily_logs(log_date, request.form)
    flash("Daily log updated.", "success")
    return _redirect_to("main.dashboard", month=month)


@bp.post("/categories/save")
def save_category():
    month = request.form.get("return_month")
    try:
        services.save_category(
            request.form.get("category_id"),
            request.form.get("name", ""),
            request.form.get("color", ""),
        )
        flash("Category saved.", "success")
    except ValueError as error:
        flash(str(error), "error")
    return _redirect_to("main.dashboard", month=month)


@bp.post("/categories/<int:category_id>/delete")
def delete_category(category_id: int):
    month = request.form.get("return_month")
    try:
        deleted = services.delete_category(category_id)
        flash(
            f"Deleted category '{deleted['name']}' and removed its {deleted['log_count']} logs.",
            "success",
        )
    except ValueError as error:
        flash(str(error), "error")
    return _redirect_to("main.dashboard", month=month)


@bp.get("/history")
def history():
    return _redirect_to("main.dashboard", month=request.args.get("month"), date=request.args.get("date"))
