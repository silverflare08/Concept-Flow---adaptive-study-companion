"""Authentication boundary and account-local study contexts for the local app."""
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse
from fastapi import BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, SecretStr, field_validator
from .auth import AuthStore, COOKIE_NAME, SESSION_SECONDS
from .account_context import account_context
from .email_delivery import send_welcome_email, welcome_email_configured


class Signup(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: str = Field(max_length=254)
    name: str = Field(min_length=1, max_length=80)
    password: SecretStr
    local_processing_consent: bool

    @field_validator("password", mode="before")
    @classmethod
    def password_length(cls, value):
        if not isinstance(value, str) or not 10 <= len(value) <= 128:
            raise ValueError("Password must contain 10-128 characters.")
        return value


class Login(BaseModel):
    identifier: str = Field(min_length=1, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)


class Preferences(BaseModel):
    theme: str = Field(default="neutral", pattern="^(neutral|lavender|sage|ocean|sand|midnight|charcoal)$")
    avatar: str = Field(default="scholar", pattern="^(scholar|explorer|owl|thinker|creator|dreamer|scholar-male|explorer-male|thinker-male)$")
    font_size: str = Field(default="normal", pattern="^(small|normal|large)$")
    language: str = Field(default="english", pattern="^(english|hindi|hinglish)$")
    explanation_depth: str = Field(default="standard", pattern="^(brief|standard|detailed)$")
    quiz_difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    education_level: str = Field(default="", max_length=80)
    subjects: str = Field(default="", max_length=300)
    learning_goals: str = Field(default="", max_length=1000)


class Profile(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    preferences: Preferences = Field(default_factory=Preferences)


class PasswordChange(BaseModel):
    current_password: SecretStr
    new_password: SecretStr = Field(min_length=10, max_length=128)


def install_auth(api):
    app = api.app

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Pydantic's default error payload can echo a submitted plaintext password.
        return JSONResponse(status_code=422, content={"detail": [
            {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
            for item in error.errors()
        ]})
    api.AUTH_REQUIRED = True
    api.AUTH_STORE = AuthStore(os.getenv("CONCEPTFLOW_AUTH_DB", "data/auth.db"))
    api.USER_DATA_ROOT = Path(os.getenv("CONCEPTFLOW_USER_DATA_DIR", "data/users"))
    api.account_states = {}
    state_lock = Lock()
    attempts = defaultdict(deque)
    attempt_lock = Lock()
    public_paths = {"/api/health", "/api/auth/signup", "/api/auth/login", "/api/auth/me"}

    def rate_limit(request):
        address = request.client.host if request.client else "unknown"
        with attempt_lock:
            queue = attempts[address]
            now = time.monotonic()
            while queue and queue[0] < now - 60:
                queue.popleft()
            if len(queue) >= 12:
                raise HTTPException(status_code=429, detail="Too many sign-in attempts. Try again in a minute.")
            queue.append(now)

    def session(request):
        result = api.AUTH_STORE.authenticate(request.cookies.get(COOKIE_NAME))
        if not result:
            raise HTTPException(status_code=401, detail="Please sign in.")
        return result

    def cookie(response, token, request):
        response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                            secure=request.url.scheme == "https", samesite="lax", path="/")

    def state_for(user):
        with state_lock:
            if user["id"] not in api.account_states:
                root = api.USER_DATA_ROOT / user["id"]
                repo = api.StudyRepository(root / "conceptflow.db")
                course_id = repo.latest_course_id() or repo.create_course("My study space")
                api.account_states[user["id"]] = {"repository": repo,
                    "workspace": api.workspace_from_record(repo.load_course(course_id)),
                    "upload_root": root / "uploads", "cache_root": root / "cache", "user_id": user["id"]}
            return api.account_states[user["id"]]

    @app.middleware("http")
    async def authentication_boundary(request, call_next):
        if not api.AUTH_REQUIRED or not request.url.path.startswith("/api/") or request.method == "OPTIONS":
            return await call_next(request)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin:
                parsed = urlparse(origin)
                same_origin = origin.rstrip("/") == str(request.base_url).rstrip("/")
                local_origin = parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1"} and request.url.hostname in {"localhost", "127.0.0.1", "testserver"}
                if not same_origin and not local_origin:
                    return JSONResponse({"detail": "This request origin is not allowed."}, status_code=403)
        if request.url.path in public_paths:
            return await call_next(request)
        identity = api.AUTH_STORE.authenticate(request.cookies.get(COOKIE_NAME))
        if not identity:
            return JSONResponse({"detail": "Please sign in to access your study space."}, status_code=401)
        state = state_for(identity["user"])
        # Request metadata lives in a new dict; mutable workspace state stays per-account.
        token = account_context.set(state)
        try:
            return await call_next(request)
        finally:
            account_context.reset(token)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.post("/api/auth/signup", status_code=201)
    def signup(data: Signup, request: Request, response: Response, background_tasks: BackgroundTasks):
        rate_limit(request)
        if not data.local_processing_consent:
            raise HTTPException(status_code=400, detail="Confirm local processing of your study data to create an account.")
        try:
            user = api.AUTH_STORE.signup(data.username, data.email, data.name, data.password.get_secret_value())
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        cookie(response, api.AUTH_STORE.create_session(user["id"], request.headers.get("user-agent", "")), request)
        enabled = welcome_email_configured()
        if enabled:
            background_tasks.add_task(send_welcome_email, user)
        return {"user": user, "welcome_email": "queued" if enabled else "not_configured"}

    @app.post("/api/auth/login")
    def login(data: Login, request: Request, response: Response):
        rate_limit(request)
        try:
            user = api.AUTH_STORE.login(data.identifier, data.password.get_secret_value())
        except ValueError as error:
            raise HTTPException(status_code=401, detail=str(error)) from error
        cookie(response, api.AUTH_STORE.create_session(user["id"], request.headers.get("user-agent", "")), request)
        return {"user": user}

    @app.get("/api/auth/me")
    def me(request: Request):
        return {"user": session(request)["user"]}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response):
        identity = session(request)
        api.AUTH_STORE.revoke(identity["user"]["id"], identity["session_id"])
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"status": "signed_out"}

    @app.get("/api/auth/sessions")
    def sessions(request: Request):
        identity = session(request)
        return {"sessions": [{**item, "current": item["id"] == identity["session_id"]}
                             for item in api.AUTH_STORE.sessions(identity["user"]["id"])]}

    @app.delete("/api/auth/sessions/{session_id}")
    def revoke_session(session_id: str, request: Request):
        identity = session(request)
        api.AUTH_STORE.revoke(identity["user"]["id"], session_id)
        return {"status": "revoked"}

    @app.post("/api/auth/logout-all")
    def logout_all(request: Request, response: Response):
        api.AUTH_STORE.revoke(session(request)["user"]["id"])
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"status": "signed_out"}

    @app.patch("/api/auth/profile")
    def profile(data: Profile, request: Request):
        identity = session(request)
        if not data.name.strip():
            raise HTTPException(status_code=400, detail="Display name cannot be blank.")
        return {"user": api.AUTH_STORE.update_profile(identity["user"]["id"], data.name, data.preferences.model_dump())}

    @app.post("/api/auth/password")
    def change_password(data: PasswordChange, request: Request, response: Response):
        try:
            api.AUTH_STORE.change_password(session(request)["user"]["id"], data.current_password.get_secret_value(), data.new_password.get_secret_value())
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"status": "password_changed", "message": "Password changed. Sign in again; all sessions were revoked."}
