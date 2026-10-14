"""Local password accounts and revocable opaque sessions; no legacy data migration."""
import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

SESSION_SECONDS = 7 * 24 * 3600
COOKIE_NAME = "conceptflow_session"


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def password_matches(password: str, encoded: str) -> bool:
    try:
        _, salt, _ = encoded.split("$")
        return hmac.compare_digest(password_hash(password, base64.b64decode(salt)), encoded)
    except (ValueError, TypeError):
        return False


class AuthStore:
    def __init__(self, path="data/auth.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL, password_hash TEXT NOT NULL,
                    preferences TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS account_sessions (
                    id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, user_id TEXT NOT NULL,
                    expires_at REAL NOT NULL, created_at REAL NOT NULL, last_seen REAL NOT NULL,
                    user_agent TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES accounts(id) ON DELETE CASCADE
                );
            ''')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def public_user(row):
        return {"id": row["id"], "username": row["username"], "email": row["email"],
                "name": row["name"], "email_verified": False,
                "preferences": json.loads(row["preferences"]), "created_at": row["created_at"]}

    def signup(self, username, email, name, password):
        username, email, name = username.strip().casefold(), email.strip().casefold(), name.strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,29}", username):
            raise ValueError("Username: use 3-30 English letters, numbers, dots, underscores or hyphens, starting with a letter or number. No spaces; for example, palak.mittal.")
        if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise ValueError("Enter a valid email address.")
        if not 10 <= len(password) <= 128:
            raise ValueError("Use a password of 10-128 characters.")
        if not 1 <= len(name) <= 80:
            raise ValueError("Enter a display name of 1-80 characters.")
        user_id = uuid4().hex
        with self.connect() as connection:
            try:
                connection.execute("INSERT INTO accounts(id,username,email,name,password_hash,preferences,created_at) VALUES(?,?,?,?,?,?,?)",
                                   (user_id, username, email, name, password_hash(password), json.dumps({"theme": "neutral"}), time.time()))
            except sqlite3.IntegrityError as error:
                raise ValueError("This username or email is already registered.") from error
            row = connection.execute("SELECT * FROM accounts WHERE id=?", (user_id,)).fetchone()
        return self.public_user(row)

    def login(self, identifier, password):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM accounts WHERE username=? OR email=?",
                                     (identifier.strip().casefold(), identifier.strip().casefold())).fetchone()
        # Perform a password derivation even for a missing account.
        encoded = row["password_hash"] if row else password_hash("not-a-real-account-password", b"0123456789abcdef")
        if not password_matches(password, encoded) or row is None:
            raise ValueError("Incorrect username/email or password.")
        return self.public_user(row)

    def create_session(self, user_id, user_agent=""):
        token, session_id, now = secrets.token_urlsafe(32), uuid4().hex, time.time()
        with self.connect() as connection:
            connection.execute("INSERT INTO account_sessions VALUES(?,?,?,?,?,?,?)", (
                session_id, hashlib.sha256(token.encode()).hexdigest(), user_id, now + SESSION_SECONDS,
                now, now, user_agent[:200]))
        return token

    def authenticate(self, token):
        if not token or len(token) > 128:
            return None
        hashed = hashlib.sha256(token.encode()).hexdigest()
        with self.connect() as connection:
            row = connection.execute('''SELECT accounts.*, account_sessions.id AS session_id
                FROM account_sessions JOIN accounts ON accounts.id=account_sessions.user_id
                WHERE token_hash=? AND expires_at>?''', (hashed, time.time())).fetchone()
            if row:
                connection.execute("UPDATE account_sessions SET last_seen=? WHERE token_hash=?", (time.time(), hashed))
        return {"user": self.public_user(row), "session_id": row["session_id"]} if row else None

    def revoke(self, user_id, session_id=None):
        with self.connect() as connection:
            if session_id:
                connection.execute("DELETE FROM account_sessions WHERE user_id=? AND id=?", (user_id, session_id))
            else:
                connection.execute("DELETE FROM account_sessions WHERE user_id=?", (user_id,))

    def sessions(self, user_id):
        with self.connect() as connection:
            rows = connection.execute("SELECT id,created_at,last_seen,user_agent,expires_at FROM account_sessions WHERE user_id=? AND expires_at>? ORDER BY last_seen DESC",
                                      (user_id, time.time())).fetchall()
        return [dict(row) for row in rows]

    def update_profile(self, user_id, name, preferences):
        with self.connect() as connection:
            connection.execute("UPDATE accounts SET name=?,preferences=? WHERE id=?", (name.strip(), json.dumps(preferences), user_id))
            row = connection.execute("SELECT * FROM accounts WHERE id=?", (user_id,)).fetchone()
        return self.public_user(row)

    def change_password(self, user_id, current, new):
        if not 10 <= len(new) <= 128:
            raise ValueError("Use a password of 10-128 characters.")
        with self.connect() as connection:
            row = connection.execute("SELECT password_hash FROM accounts WHERE id=?", (user_id,)).fetchone()
            if not row or not password_matches(current, row[0]):
                raise ValueError("Current password is incorrect.")
            connection.execute("UPDATE accounts SET password_hash=? WHERE id=?", (password_hash(new), user_id))
            connection.execute("DELETE FROM account_sessions WHERE user_id=?", (user_id,))
