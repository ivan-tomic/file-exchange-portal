#!/usr/bin/env python3
"""
Business Reporter - File Exchange Portal
A Flask application for secure file exchange with role-based access control.
"""

import json
import sqlite3
import shutil
import datetime as dt
from pathlib import Path
from functools import wraps
import re

from werkzeug.security import generate_password_hash, check_password_hash
from flask import (
    Flask, request, redirect, url_for, render_template, session,
    send_from_directory, flash, abort
)

# Import configuration
from config import (
    APP_NAME, FILES_DIR, AUDIT_LOG, INDEX_FILE, USER_DB_PATH, 
    SECRET_KEY, PORT, ALLOWED_EXT, MAX_CONTENT_LENGTH, 
    SESSION_COOKIE_SECURE, STAGE_CHOICES, STAGE_ALIASES, 
    DASHBOARD_URL, INV_CHARS, INVITE_CODE
)
# Import email utilities
from email_utils import notify_file_upload

# -------------------- Flask App Setup --------------------
app = Flask(__name__)
app.config.update(
    SECRET_KEY=SECRET_KEY,
    MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=SESSION_COOKIE_SECURE,
)

# -------------------- Helper Functions --------------------
def log_event(user: str, action: str, detail: str = "") -> None:
    """Log an event to the audit log."""
    ts = dt.datetime.utcnow().isoformat() + "Z"
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{ts}\t{user}\t{action}\t{detail}\n")

def login_required(view):
    """Decorator to require login for a view."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if session.get("logged_in") is True:
            return view(*args, **kwargs)
        return redirect(url_for("login", next=request.path))
    return wrapper

def role_required(role):
    """Decorator to require a specific role for a view."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if session.get("logged_in"):
                r = session.get("role")
                if r == role or (role == "admin" and r == "super"):
                    return view(*args, **kwargs)
            abort(403)
        return wrapper
    return decorator

def is_safe_filename(filename: str) -> bool:
    """Check if a filename is safe."""
    return bool(re.fullmatch(r"[\w,\-\.\ ]+\.zip", filename, flags=re.IGNORECASE))

def normalize_stage(value):
    """Normalize stage values and handle legacy mappings."""
    if value is None:
        return STAGE_CHOICES[0]
    v = str(value).strip()
    if v == "":
        return ""
    v = STAGE_ALIASES.get(v, v)
    return v if v in STAGE_CHOICES else STAGE_CHOICES[0]

def load_index() -> dict:
    """Load the file index from JSON."""
    if INDEX_FILE.exists():
        try:
            data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            for _, meta in list(data.items()):
                if isinstance(meta, dict):
                    meta["stage"] = normalize_stage(meta.get("stage"))
                    if "note" not in meta:
                        nb = meta.get("notes_by") or {}
                        for _u, n in nb.items():
                            if str(n).strip():
                                meta["note"] = str(n).strip()[:100]
                                break
                        else:
                            meta["note"] = ""
                    else:
                        meta["note"] = str(meta["note"]).strip()[:100]
                    meta.setdefault("note_by", "")
                    meta.setdefault("note_at", "")
            return data
        except Exception:
            return {}
    return {}

def save_index(data: dict) -> None:
    """Save the file index to JSON."""
    for _, meta in list(data.items()):
        if isinstance(meta, dict):
            meta["stage"] = normalize_stage(meta.get("stage"))
            meta["note"] = str(meta.get("note", "") or "").strip()[:100]
            meta["note_by"] = str(meta.get("note_by", "") or "").strip()
            meta["note_at"] = str(meta.get("note_at", "") or "").strip()
    INDEX_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def urgency_rank(urgency: str) -> int:
    """Return sort rank for urgency (High first)."""
    return 0 if urgency == "High" else 1

def visible_files_for(_user: str, _role: str):
    """Get list of visible files for a user."""
    return [p for p in FILES_DIR.glob("*.zip") if p.is_file()]

def sort_rows(rows):
    """Sort rows by urgency and modification time."""
    rows.sort(key=lambda r: (urgency_rank(r["urgency"]), -r["mtime"].timestamp()))
    return rows

def meta_get_uploader_role(meta: dict) -> str:
    """Get the role of the uploader from metadata."""
    role = meta.get("uploader_role")
    if role in {"user", "admin", "super"}:
        return role
    uploader = meta.get("uploader")
    if uploader:
        u = get_user(uploader)
        if u:
            return u["role"]
    return "admin"

# -------------------- Database Functions --------------------
def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(USER_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_db():
    """Ensure database tables exist."""
    with get_db() as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT UNIQUE NOT NULL,
          email TEXT,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('super','admin','user')) DEFAULT 'user',
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL
        )""")
        db.execute("""
        CREATE TABLE IF NOT EXISTS invites (
          code TEXT PRIMARY KEY,
          is_used INTEGER NOT NULL DEFAULT 0,
          used_by TEXT,
          used_at TEXT,
          created_at TEXT NOT NULL
        )""")

def get_user(username):
    """Get a user by username."""
    with get_db() as db:
        return db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()

def list_users():
    """List all users."""
    with get_db() as db:
        return db.execute("SELECT id, username, email, role, is_active, created_at FROM users ORDER BY created_at DESC").fetchall()

def create_user(username, password, role="user", email=None):
    """Create a new user."""
    ph = generate_password_hash(password)
    created = dt.datetime.utcnow().isoformat() + "Z"
    with get_db() as db:
        db.execute(
            "INSERT INTO users (username, email, password_hash, role, is_active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (username, email, ph, role, created)
        )

def set_role(username, role):
    """Set a user's role."""
    with get_db() as db:
        db.execute("UPDATE users SET role=? WHERE username=?", (role, username))

def set_active(username, active: int):
    """Set a user's active status."""
    with get_db() as db:
        db.execute("UPDATE users SET is_active=? WHERE username=?", (1 if active else 0, username))

def set_password(username, new_password):
    """Set a user's password."""
    ph = generate_password_hash(new_password)
    with get_db() as db:
        db.execute("UPDATE users SET password_hash=? WHERE username=?", (ph, username))

def delete_user(username):
    """Delete a user."""
    with get_db() as db:
        db.execute("DELETE FROM users WHERE username=?", (username,))

def count_supers():
    """Count active superusers."""
    with get_db() as db:
        r = db.execute("SELECT COUNT(*) AS n FROM users WHERE role='super' AND is_active=1").fetchone()
        return int(r["n"])

# -------------------- Invite Functions --------------------
def create_invite_codes(n=10, length=7):
    """Create invite codes."""
    import secrets
    now = dt.datetime.utcnow().isoformat() + "Z"
    codes = []
    with get_db() as db:
        for _ in range(max(1, min(int(n), 100))):
            while True:
                code = "".join(secrets.choice(INV_CHARS) for _ in range(max(5, min(int(length), 10))))
                exists = db.execute("SELECT 1 FROM invites WHERE code=?", (code,)).fetchone()
                if not exists:
                    break
            db.execute("INSERT INTO invites (code, is_used, created_at) VALUES (?, 0, ?)", (code, now))
            codes.append(code)
    return codes

def list_invites():
    """List all invites."""
    with get_db() as db:
        return db.execute("SELECT code, is_used, used_by, used_at, created_at FROM invites ORDER BY created_at DESC").fetchall()

def revoke_invite(code):
    """Revoke an unused invite."""
    with get_db() as db:
        db.execute("DELETE FROM invites WHERE code=? AND is_used=0", (code,))

def invites_available():
    """Check if any invites are available."""
    with get_db() as db:
        r = db.execute("SELECT COUNT(*) AS n FROM invites WHERE is_used=0").fetchone()
        return int(r["n"]) > 0

def invite_is_valid(code):
    """Check if an invite code is valid."""
    if not code:
        return False
    if INVITE_CODE and code == INVITE_CODE:
        return True
    with get_db() as db:
        r = db.execute("SELECT is_used FROM invites WHERE code=?", (code,)).fetchone()
        return bool(r) and int(r["is_used"]) == 0

def consume_invite(code, username):
    """Mark an invite as used."""
    if INVITE_CODE and code == INVITE_CODE:
        return
    now = dt.datetime.utcnow().isoformat() + "Z"
    with get_db() as db:
        db.execute(
            "UPDATE invites SET is_used=1, used_by=?, used_at=? WHERE code=? AND is_used=0",
            (username, now, code)
        )

# Initialize database
ensure_db()

# -------------------- Routes: Authentication --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        u = get_user(username)
        if u and u["is_active"] and check_password_hash(u["password_hash"], password):
            session["logged_in"] = True
            session["user"] = username
            session["role"] = u["role"]
            log_event(username, "login", u["role"])
            return redirect(request.args.get("next") or url_for("index"))
        flash("Invalid credentials.", "error")
    return render_template("login.html", app_name=APP_NAME)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Registration page."""
    if session.get("logged_in"):
        return redirect(url_for("index"))

    invite_required = bool(INVITE_CODE) or invites_available()
    if request.method == "POST":
        invite = request.form.get("invite", "").strip()
        if invite_required and not (invite and invite_is_valid(invite)):
            flash("Invalid invite code.", "error")
            return redirect(url_for("register"))

        username = request.form.get("username", "").strip()
        email = (request.form.get("email") or "").strip() or None
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
            return redirect(url_for("register"))
        if get_user(username):
            flash("Username already taken.", "error")
            return redirect(url_for("register"))

        create_user(username, password, role="user", email=email)
        if invite_required:
            consume_invite(invite, username)

        session["logged_in"] = True
        session["user"] = username
        session["role"] = "user"
        flash("Welcome! Account created.", "ok")
        log_event(username, "register", "user")
        return redirect(url_for("index"))

    return render_template("register.html", app_name=APP_NAME, invite_required=invite_required)

@app.route("/logout")
@login_required
def logout():
    """Logout."""
    u = session.get("user", "?")
    session.clear()
    log_event(u, "logout")
    return redirect(url_for("login"))

# -------------------- Routes: Main Application --------------------
@app.route("/")
@login_required
def index():
    """Main file listing page."""
    role = session.get("role", "user")
    user = session.get("user", "?")
    idx = load_index()

    rows = []
    for p in visible_files_for(user, role):
        stat = p.stat()
        meta = idx.get(p.name, {}) or {}
        urgency = meta.get("urgency", "Normal")
        stage = normalize_stage(meta.get("stage"))
        reviewed = bool((meta.get("reviewed_by") or {}).get(user))
        note = meta.get("note", "")
        note_by = meta.get("note_by", "")
        note_at = meta.get("note_at", "")
        uploader_role = meta_get_uploader_role(meta)

        rows.append({
            "name": p.name,
            "size": stat.st_size,
            "mtime": dt.datetime.fromtimestamp(stat.st_mtime),
            "urgency": urgency,
            "stage": stage,
            "reviewed": reviewed,
            "note": note,
            "note_by": note_by,
            "note_at": note_at,
            "uploader_role": uploader_role,
        })

    admin_rows = sort_rows([r for r in rows if r["uploader_role"] != "user"])
    user_rows  = sort_rows([r for r in rows if r["uploader_role"] == "user"])

    def can_delete(r):
        if role in ("admin", "super"):
            return True
        return r["uploader_role"] == "user"

    for r in admin_rows + user_rows:
        r["can_delete"] = can_delete(r)

    return render_template(
        "index.html",
        admin_rows=admin_rows, 
        user_rows=user_rows,
        app_name=APP_NAME, 
        role=role, 
        user=user,
        stage_choices=STAGE_CHOICES, 
        dashboard_url=DASHBOARD_URL
    )

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    """Handle file upload."""
    f = request.files.get("file")
    if not f or f.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("index"))
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_EXT:
        flash("Only .zip files are allowed.", "error")
        return redirect(url_for("index"))

    safe_name = re.sub(r"[^\w\-. ]+", "_", f.filename)
    dest = FILES_DIR / safe_name

    role = session.get("role", "user")

    if role == "user":
        urgency = "Normal"
        stage = ""
    else:
        urgency = request.form.get("urgency", "Normal").strip().title()
        if urgency not in {"High", "Normal"}:
            urgency = "Normal"
        stage = normalize_stage(request.form.get("stage", STAGE_CHOICES[0]).strip())

    f.save(dest)

    idx = load_index()
    idx[safe_name] = {
        "uploader": session.get("user", "?"),
        "uploader_role": role,
        "uploaded_at": dt.datetime.utcnow().isoformat() + "Z",
        "urgency": urgency,
        "stage": stage,
        "reviewed_by": {},
        "note": "",
        "note_by": "",
        "note_at": "",
    }
    save_index(idx)

    log_event(session.get("user", "?"), "upload", f"{safe_name} (urgency={urgency}, stage={stage or '[blank]'})")
    flash(f"Uploaded {safe_name}", "ok")
    
    # Send email notifications
    try:
        recipient_emails = []
        
        if role == "user":
            # User uploaded: notify all admin and super users
            with get_db() as db:
                admins = db.execute(
                    "SELECT email FROM users WHERE (role='admin' OR role='super') AND is_active=1 AND email IS NOT NULL AND email != ''"
                ).fetchall()
                recipient_emails = [admin["email"] for admin in admins]
        else:
            # Admin/super uploaded: notify all users with emails
            with get_db() as db:
                users = db.execute(
                    "SELECT email FROM users WHERE role='user' AND is_active=1 AND email IS NOT NULL AND email != ''"
                ).fetchall()
                recipient_emails = [user["email"] for user in users]
        
        if recipient_emails:
            notify_file_upload(
                filename=safe_name,
                uploader=session.get("user", "?"),
                uploader_role=role,
                recipient_emails=recipient_emails,
                urgency=urgency,
                stage=stage
            )
    except Exception as e:
        # Log error but don't fail the upload
        print(f"Email notification failed: {e}")
    
    return redirect(url_for("index"))

@app.route("/set_urgency/<path:filename>", methods=["POST"])
@login_required
@role_required("admin")
def set_urgency(filename):
    """Set file urgency."""
    if not is_safe_filename(filename):
        abort(400)
    path = FILES_DIR / filename
    if not path.exists():
        abort(404)

    idx = load_index()
    meta = idx.get(filename) or {}
    if meta_get_uploader_role(meta) == "user":
        flash("Cannot change urgency for files uploaded by Amazon users.", "error")
        return redirect(url_for("index"))

    new_urg = request.form.get("urgency", "Normal").strip().title()
    if new_urg not in {"High", "Normal"}:
        new_urg = "Normal"

    meta["urgency"] = new_urg
    idx[filename] = meta
    save_index(idx)

    log_event(session.get("user", "?"), "set_urgency", f"{filename} -> {new_urg}")
    flash(f"Updated urgency for {filename} to {new_urg}", "ok")
    return redirect(url_for("index"))

@app.route("/set_stage/<path:filename>", methods=["POST"])
@login_required
@role_required("admin")
def set_stage(filename):
    """Set file stage."""
    if not is_safe_filename(filename):
        abort(400)
    path = FILES_DIR / filename
    if not path.exists():
        abort(404)

    idx = load_index()
    meta = idx.get(filename) or {}
    if meta_get_uploader_role(meta) == "user":
        flash("Cannot change stage for files uploaded by Amazon users.", "error")
        return redirect(url_for("index"))

    new_stage = normalize_stage(request.form.get("stage", STAGE_CHOICES[0]).strip())
    meta["stage"] = new_stage
    idx[filename] = meta
    save_index(idx)

    log_event(session.get("user", "?"), "set_stage", f"{filename} -> {new_stage or '[blank]'}")
    flash(f'Updated stage for {filename} to "{new_stage or "—"}".', "ok")
    return redirect(url_for("index"))

@app.route("/toggle_reviewed/<path:filename>", methods=["POST"])
@login_required
def toggle_reviewed(filename):
    """Toggle reviewed status."""
    if session.get("role") != "user":
        abort(403)

    if not is_safe_filename(filename):
        abort(400)
    path = FILES_DIR / filename
    if not path.exists():
        abort(404)

    idx = load_index()
    meta = idx.get(filename) or {}
    if meta_get_uploader_role(meta) == "user":
        flash("Reviewed is not required for files uploaded by Amazon users.", "error")
        return redirect(url_for("index"))

    checked = "1" in request.form.getlist("checked")

    rb = meta.get("reviewed_by") or {}
    rb[session.get("user", "?")] = bool(checked)
    meta["reviewed_by"] = rb
    idx[filename] = meta
    save_index(idx)

    return redirect(url_for("index"))

@app.route("/set_note/<path:filename>", methods=["POST"])
@login_required
def set_note(filename):
    """Set note for a file."""
    if not is_safe_filename(filename):
        abort(400)
    path = FILES_DIR / filename
    if not path.exists():
        abort(404)

    note = (request.form.get("note") or "").strip()
    if len(note) > 100:
        note = note[:100]
        flash("Note truncated to 100 characters.", "error")

    idx = load_index()
    meta = idx.get(filename) or {}
    meta["note"] = note
    meta["note_by"] = session.get("user", "?")
    meta["note_at"] = dt.datetime.utcnow().isoformat() + "Z"
    idx[filename] = meta
    save_index(idx)

    flash("Note saved.", "ok")
    return redirect(url_for("index"))

@app.route("/download/<path:filename>")
@login_required
def download(filename):
    """Download a file."""
    if not is_safe_filename(filename):
        abort(400)
    path = FILES_DIR / filename
    if not path.exists():
        abort(404)
    return send_from_directory(FILES_DIR, filename, as_attachment=True)

@app.route("/approve/<path:filename>", methods=["POST"])
@login_required
@role_required("admin")
def approve(filename):
    """Archive/approve a file."""
    if not is_safe_filename(filename):
        abort(400)
    src = FILES_DIR / filename
    if not src.exists():
        abort(404)

    approved_dir = FILES_DIR / "_approved"
    approved_dir.mkdir(parents=True, exist_ok=True)

    target = approved_dir / filename
    if target.exists():
        ts = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        stem, suffix = Path(filename).stem, Path(filename).suffix
        target = approved_dir / f"{stem}__approved_{ts}{suffix}"

    shutil.move(str(src), str(target))

    idx = load_index()
    idx.pop(filename, None)
    save_index(idx)

    log_event(session.get("user", "?"), "approve_archive", f"{filename} -> {target.name}")
    flash(f"Archived {filename} to _approved/", "ok")
    return redirect(url_for("index"))

@app.route("/delete/<path:filename>", methods=["POST"])
@login_required
def delete_file(filename):
    """Delete a file."""
    if not is_safe_filename(filename):
        abort(400)
    path = FILES_DIR / filename
    if not path.exists():
        abort(404)

    idx = load_index()
    meta = idx.get(filename) or {}
    uploader_role = meta_get_uploader_role(meta)
    role = session.get("role", "user")

    if not (role in ("admin", "super") or uploader_role == "user"):
        abort(403)

    path.unlink(missing_ok=True)
    idx.pop(filename, None)
    save_index(idx)

    log_event(session.get("user", "?"), "delete", filename)
    flash(f"Deleted {filename}", "ok")
    return redirect(url_for("index"))

# -------------------- Routes: Admin (User Management) --------------------
@app.route("/admin/users", methods=["GET"])
@login_required
def admin_users():
    """User management page."""
    if session.get("role") != "super":
        abort(403)
    rows = list_users()
    invites = list_invites()
    return render_template(
        "admin_users.html", 
        users=rows, 
        invites=invites, 
        app_name=APP_NAME, 
        dashboard_url=DASHBOARD_URL
    )

@app.route("/admin/users/action", methods=["POST"])
@login_required
def admin_users_action():
    """Handle user management actions."""
    if session.get("role") != "super":
        abort(403)
    action = request.form.get("action")
    username = request.form.get("username")

    try:
        if action in {"promote", "demote", "make_super", "deactivate", "activate", "reset_password", "delete_user"}:
            if not username or not get_user(username):
                flash("Unknown user.", "error")
                return redirect(url_for("admin_users"))

        if action == "promote":
            set_role(username, "admin")
            flash(f"Promoted {username} to admin", "ok")
        elif action == "demote":
            if username == session.get("user"):
                flash("Refusing to demote the current superuser.", "error")
            else:
                set_role(username, "user")
                flash(f"Demoted {username} to user", "ok")
        elif action == "make_super":
            set_role(username, "super")
            flash(f"Granted super role to {username}", "ok")
        elif action == "deactivate":
            if username == session.get("user"):
                flash("Refusing to deactivate the current superuser.", "error")
            else:
                set_active(username, 0)
                flash(f"Deactivated {username}", "ok")
        elif action == "activate":
            set_active(username, 1)
            flash(f"Activated {username}", "ok")
        elif action == "reset_password":
            newpw = request.form.get("new_password", "")
            if len(newpw) < 6:
                flash("New password must be at least 6 characters.", "error")
            else:
                set_password(username, newpw)
                flash(f"Password reset for {username}", "ok")
        elif action == "delete_user":
            if username == session.get("user"):
                flash("Refusing to delete the current superuser.", "error")
            else:
                u = get_user(username)
                if u and u["role"] == "super" and count_supers() <= 1:
                    flash("Cannot delete the last active superuser.", "error")
                else:
                    delete_user(username)
                    flash(f"Deleted user {username}", "ok")
        elif action == "gen_invites":
            n = int(request.form.get("count", "10") or "10")
            length = int(request.form.get("length", "7") or "7")
            n = max(1, min(n, 50))
            length = max(5, min(length, 10))
            codes = create_invite_codes(n=n, length=length)
            flash("Generated: " + ", ".join(codes), "ok")
        elif action == "revoke_invite":
            code = request.form.get("code", "")
            revoke_invite(code)
            flash(f"Revoked {code}", "ok")
        else:
            flash("Unknown action.", "error")
    except sqlite3.IntegrityError:
        flash("Operation failed due to a constraint.", "error")

    return redirect(url_for("admin_users"))

# -------------------- Run Application --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)