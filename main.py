import logging
import os
import re
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv
from flask import Flask, jsonify, make_response, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("users-api")

# ---------------------------------------------------------------------------
# App & Config
# ---------------------------------------------------------------------------
app = Flask(__name__)


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///users.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,          # detect stale connections
        "pool_recycle": 300,
    }
    API_KEY = os.getenv("API_KEY")
    MAX_CONTENT_LENGTH = 16 * 1024      # 16 KB – enough for user payloads
    JSON_SORT_KEYS = False


app.config.from_object(Config)

db = SQLAlchemy(app)

EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    email: Mapped[str] = mapped_column(
        db.String(150), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email}>"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def error_response(message: str, status: int = 400) -> tuple:
    """Uniform error envelope used everywhere."""
    return jsonify({"error": message}), status


def parse_user_data(
    data: Any, *, partial: bool = False
) -> Tuple[Optional[Dict[str, str]], Optional[Tuple[str, int]]]:
    """Validate and normalise name / email. Returns (fields, error)."""
    if not isinstance(data, dict):
        return None, ("JSON object with user data is required", 400)

    if partial and not data:
        return None, ("At least one of name or email is required", 400)

    fields: Dict[str, str] = {}

    if not partial or "name" in data:
        name = data.get("name")
        if not isinstance(name, str) or not (name := name.strip()):
            return None, ("name must be a non-empty string", 400)
        if len(name) > 100:
            return None, ("name must be at most 100 characters", 400)
        fields["name"] = name

    if not partial or "email" in data:
        email = data.get("email")
        if not isinstance(email, str) or not (
            email := email.strip().lower()
        ) or not EMAIL_PATTERN.fullmatch(email):
            return None, ("email must be a valid email address", 400)
        if len(email) > 150:
            return None, ("email must be at most 150 characters", 400)
        fields["email"] = email

    if partial and not fields:
        return None, ("At least one of name or email is required", 400)

    return fields, None


def email_in_use(email: str, exclude_id: Optional[int] = None) -> bool:
    stmt = select(User.id).where(User.email == email)
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    return db.session.execute(stmt).scalar_one_or_none() is not None


def require_api_key(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        expected = app.config.get("API_KEY")
        if not expected:
            logger.error("API_KEY is not configured")
            return error_response("API_KEY is not configured", 503)
        provided = request.headers.get("X-API-Key")
        if not provided or provided != expected:
            return error_response("Invalid or missing API key", 401)
        return view(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(IntegrityError)
def handle_integrity_error(exc: IntegrityError):
    db.session.rollback()
    logger.warning("IntegrityError: %s", exc)
    return error_response("The request conflicts with existing data", 409)


@app.errorhandler(404)
def not_found(_):
    return error_response("Resource not found", 404)


@app.errorhandler(405)
def method_not_allowed(_):
    return error_response("Method not allowed", 405)


@app.errorhandler(413)
def payload_too_large(_):
    return error_response("Payload too large", 413)


@app.errorhandler(500)
def internal_error(exc):
    db.session.rollback()
    logger.exception("Unhandled exception")
    return error_response("Internal server error", 500)


# ---------------------------------------------------------------------------
# Routes – public
# ---------------------------------------------------------------------------
@app.get("/api")
def home():
    return jsonify({"message": "Flask CRUD API is running"}), 200


@app.get("/health")
def health():
    """Lightweight readiness / liveness probe."""
    try:
        db.session.execute(select(1))
        return jsonify({"status": "ok"}), 200
    except Exception:
        logger.exception("Health check failed")
        return error_response("Database unavailable", 503)


@app.get("/")
def dashboard():
    response = make_response(render_template("index.html"))
    response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------
# Routes – Users
# ---------------------------------------------------------------------------
@app.get("/users")
def get_users():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    sort = request.args.get("sort", "id").lower()
    order = request.args.get("order", "asc").lower()

    if page < 1 or not (1 <= per_page <= 100):
        return error_response(
            "page must be >= 1 and per_page must be between 1 and 100"
        )

    allowed_sort = {"id", "name", "email", "created_at", "updated_at"}
    if sort not in allowed_sort:
        return error_response(f"sort must be one of {sorted(allowed_sort)}")
    if order not in {"asc", "desc"}:
        return error_response("order must be 'asc' or 'desc'")

    column = getattr(User, sort)
    order_by = column.desc() if order == "desc" else column.asc()

    pagination = (
        db.paginate(
            select(User).order_by(order_by),
            page=page,
            per_page=per_page,
            error_out=False,
        )
    )

    return jsonify(
        {
            "items": [u.to_dict() for u in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        }
    ), 200


@app.get("/users/<int:user_id>")
def get_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return error_response("User not found", 404)
    return jsonify(user.to_dict()), 200


@app.post("/users")
@require_api_key
def create_user():
    if not request.is_json:
        return error_response("Content-Type must be application/json")

    fields, err = parse_user_data(request.get_json(silent=True))
    if err:
        return error_response(*err)

    if email_in_use(fields["email"]):
        return error_response("Email already exists", 409)

    user = User(**fields)
    db.session.add(user)
    db.session.commit()
    logger.info("Created user id=%s email=%s", user.id, user.email)
    return jsonify(user.to_dict()), 201


@app.put("/users/<int:user_id>")
@require_api_key
def update_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return error_response("User not found", 404)

    if not request.is_json:
        return error_response("Content-Type must be application/json")

    fields, err = parse_user_data(request.get_json(silent=True))
    if err:
        return error_response(*err)

    if email_in_use(fields["email"], exclude_id=user_id):
        return error_response("Email already exists", 409)

    user.name = fields["name"]
    user.email = fields["email"]
    db.session.commit()
    logger.info("Updated user id=%s", user.id)
    return jsonify(user.to_dict()), 200


@app.patch("/users/<int:user_id>")
@require_api_key
def patch_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return error_response("User not found", 404)

    if not request.is_json:
        return error_response("Content-Type must be application/json")

    fields, err = parse_user_data(request.get_json(silent=True), partial=True)
    if err:
        return error_response(*err)

    if "email" in fields and email_in_use(fields["email"], exclude_id=user_id):
        return error_response("Email already exists", 409)

    for key, value in fields.items():
        setattr(user, key, value)

    db.session.commit()
    logger.info("Patched user id=%s fields=%s", user.id, list(fields))
    return jsonify(user.to_dict()), 200


@app.delete("/users/<int:user_id>")
@require_api_key
def delete_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return error_response("User not found", 404)

    deleted = user.to_dict()
    db.session.delete(user)
    db.session.commit()
    logger.info("Deleted user id=%s", user_id)
    return jsonify({"message": "User deleted successfully", "user": deleted}), 200


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))