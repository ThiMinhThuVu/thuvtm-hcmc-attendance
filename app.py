import csv
import hashlib
import hmac
import io
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", BASE_DIR / "data" / "students.db"))
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
STUDENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{3,30}$")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", secrets.token_hex(32)),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.getenv("RENDER")) or os.getenv("SESSION_COOKIE_SECURE") == "1",
    MAX_CONTENT_LENGTH=16 * 1024,
)


def get_db():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db():
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                student_id TEXT NOT NULL COLLATE NOCASE UNIQUE,
                email TEXT NOT NULL,
                in_hcmc INTEGER NOT NULL CHECK (in_hcmc IN (0, 1)),
                attendance TEXT NOT NULL CHECK (attendance IN ('yes', 'no', 'unsure')),
                reason TEXT NOT NULL DEFAULT '',
                edit_token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def clean_payload(data):
    full_name = str(data.get("full_name", "")).strip()
    student_id = str(data.get("student_id", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    in_hcmc = data.get("in_hcmc")
    attendance = str(data.get("attendance", "")).strip()
    reason = str(data.get("reason", "")).strip()

    errors = {}
    if len(full_name) < 2 or len(full_name) > 120:
        errors["full_name"] = "Enter a name between 2 and 120 characters."
    if not STUDENT_ID_RE.fullmatch(student_id):
        errors["student_id"] = "Use 3–30 letters, numbers, dots, dashes, or underscores."
    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        errors["email"] = "Enter a valid email address."
    if in_hcmc not in (True, False):
        errors["in_hcmc"] = "Choose whether you are currently in Ho Chi Minh City."
    if attendance not in {"yes", "no", "unsure"}:
        errors["attendance"] = "Choose an attendance option."
    if len(reason) > 500:
        errors["reason"] = "Keep the note under 500 characters."
    return {
        "full_name": full_name,
        "student_id": student_id,
        "email": email,
        "in_hcmc": int(bool(in_hcmc)),
        "attendance": attendance,
        "reason": reason,
    }, errors


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; img-src 'self' data:; base-uri 'self'; form-action 'self'"
    )
    return response


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.post("/api/students")
def create_student():
    payload, errors = clean_payload(request.get_json(silent=True) or {})
    if errors:
        return jsonify(error="Please check the highlighted fields.", fields=errors), 400

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_db() as db:
            db.execute(
                """INSERT INTO students
                   (full_name, student_id, email, in_hcmc, attendance, reason,
                    edit_token_hash, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*payload.values(), token_hash(token), now, now),
            )
    except sqlite3.IntegrityError:
        return jsonify(error="This student ID has already been submitted. Use your private edit link to update it."), 409
    return jsonify(message="Your response has been saved.", edit_token=token), 201


@app.get("/api/students/me")
def get_student():
    token = request.args.get("token", "")
    if len(token) < 32:
        return jsonify(error="Invalid edit link."), 404
    with get_db() as db:
        row = db.execute(
            """SELECT full_name, student_id, email, in_hcmc, attendance, reason
               FROM students WHERE edit_token_hash = ?""",
            (token_hash(token),),
        ).fetchone()
    if not row:
        return jsonify(error="This edit link is invalid or no longer available."), 404
    result = dict(row)
    result["in_hcmc"] = bool(result["in_hcmc"])
    return jsonify(result)


@app.put("/api/students/me")
def update_student():
    data = request.get_json(silent=True) or {}
    token = str(data.pop("edit_token", ""))
    payload, errors = clean_payload(data)
    if len(token) < 32:
        return jsonify(error="Invalid edit link."), 404
    if errors:
        return jsonify(error="Please check the highlighted fields.", fields=errors), 400
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_db() as db:
            cursor = db.execute(
                """UPDATE students SET full_name=?, student_id=?, email=?, in_hcmc=?,
                   attendance=?, reason=?, updated_at=? WHERE edit_token_hash=?""",
                (*payload.values(), now, token_hash(token)),
            )
    except sqlite3.IntegrityError:
        return jsonify(error="That student ID is already used by another response."), 409
    if cursor.rowcount == 0:
        return jsonify(error="This edit link is invalid or no longer available."), 404
    return jsonify(message="Your response has been updated.")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        expected = os.getenv("ADMIN_PASSWORD", "")
        supplied = request.form.get("password", "")
        if expected and hmac.compare_digest(supplied, expected):
            session.clear()
            session["admin"] = True
            return redirect(url_for("admin"))
        error = "Incorrect password."
    return render_template("login.html", error=error)


@app.post("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))


@app.get("/admin")
@admin_required
def admin():
    with get_db() as db:
        rows = db.execute(
            """SELECT full_name, student_id, email, in_hcmc, attendance, reason,
                      created_at, updated_at FROM students ORDER BY updated_at DESC"""
        ).fetchall()
    students = [dict(row) for row in rows]
    summary = {
        "total": len(students),
        "in_hcmc": sum(s["in_hcmc"] for s in students),
        "cannot_attend": sum(s["attendance"] == "no" for s in students),
        "hcmc_cannot_attend": sum(s["in_hcmc"] and s["attendance"] == "no" for s in students),
    }
    return render_template("admin.html", students=students, summary=summary)


@app.get("/admin/export.csv")
@admin_required
def export_csv():
    with get_db() as db:
        rows = db.execute(
            """SELECT full_name, student_id, email, in_hcmc, attendance, reason,
                      created_at, updated_at FROM students ORDER BY full_name COLLATE NOCASE"""
        ).fetchall()
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["Full name", "Student ID", "Email", "In HCMC", "Can attend in person", "Note", "Created (UTC)", "Updated (UTC)"])
    labels = {"yes": "Yes", "no": "No", "unsure": "Not sure"}
    for row in rows:
        writer.writerow([row["full_name"], row["student_id"], row["email"], "Yes" if row["in_hcmc"] else "No", labels[row["attendance"]], row["reason"], row["created_at"], row["updated_at"]])
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=thuvtm-hcmc-students.csv"},
    )


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=os.getenv("FLASK_DEBUG") == "1")
