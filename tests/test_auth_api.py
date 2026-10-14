from fastapi.testclient import TestClient
from studybuddy import api
from studybuddy.auth import AuthStore


def test_signup_isolation_and_logout(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "AUTH_STORE", AuthStore(tmp_path / "auth.db"))
    monkeypatch.setattr(api, "USER_DATA_ROOT", tmp_path / "users")
    monkeypatch.setattr(api, "account_states", {})
    first, second = TestClient(api.app), TestClient(api.app)
    assert first.get("/api/workspace").status_code == 401
    def signup(client, name):
        return client.post("/api/auth/signup", json={"username": name, "email": f"{name}@example.com", "name": name,
            "password": "a-long-password", "local_processing_consent": True})
    response = signup(first, "alice")
    assert response.status_code == 201, response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    assert signup(second, "bob").status_code == 201
    assert first.post("/api/workspace", json={"name": "Alice private course"}).status_code == 200
    assert first.get("/api/workspace").json()["name"] == "Alice private course"
    private_id = first.get("/api/workspace").json()["id"]
    assert second.post(f"/api/courses/{private_id}/activate").status_code == 404
    assert second.delete(f"/api/courses/{private_id}").status_code == 404
    assert second.get("/api/workspace").json()["name"] != "Alice private course"
    updated = first.patch("/api/auth/profile", json={"name": "Alice Updated", "preferences": {"language": "hindi", "quiz_difficulty": "easy", "font_size": "small", "theme": "midnight", "avatar": "creator"}})
    assert updated.status_code == 200
    assert first.get("/api/auth/me").json()["user"]["preferences"]["font_size"] == "small"
    assert first.get("/api/auth/me").json()["user"]["preferences"]["theme"] == "midnight"
    assert first.get("/api/auth/me").json()["user"]["preferences"]["avatar"] == "creator"
    charcoal = first.patch("/api/auth/profile", json={"name": "Alice Updated", "preferences": {"theme": "charcoal", "avatar": "scholar-male"}})
    assert charcoal.status_code == 200
    assert first.get("/api/auth/me").json()["user"]["preferences"]["theme"] == "charcoal"
    assert first.get("/api/auth/me").json()["user"]["preferences"]["avatar"] == "scholar-male"
    owl = first.patch("/api/auth/profile", json={"name": "Alice Updated", "preferences": {"avatar": "owl"}})
    assert owl.status_code == 200
    assert first.get("/api/auth/me").json()["user"]["preferences"]["avatar"] == "owl"
    invalid = first.patch("/api/auth/profile", json={"name": "Alice", "preferences": {"theme": "invalid", "avatar": "unknown"}})
    assert invalid.status_code == 422
    assert second.get("/api/auth/me").json()["user"]["name"] == "bob"
    assert first.post("/api/auth/logout").status_code == 200
    assert first.get("/api/workspace").status_code == 401
    assert second.get("/api/workspace").status_code == 200


def test_reject_foreign_origin():
    client = TestClient(api.app)
    assert client.post("/api/auth/login", headers={"Origin": "https://untrusted.example"},
        json={"identifier": "alice", "password": "a-long-password"}).status_code == 403


def test_short_password_has_clear_message_without_echoing_secret():
    response = TestClient(api.app).post("/api/auth/signup", json={"username": "sample", "email": "sample@example.com", "name": "Sample", "password": "short123", "local_processing_consent": True})
    assert response.status_code == 422
    assert "10-128 characters" in response.text
    assert "short123" not in response.text


def test_password_settings_revoke_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "AUTH_STORE", AuthStore(tmp_path / "auth.db"))
    monkeypatch.setattr(api, "USER_DATA_ROOT", tmp_path / "users")
    monkeypatch.setattr(api, "account_states", {})
    client = TestClient(api.app)
    response = client.post("/api/auth/signup", json={"username": "settings_user", "email": "settings@example.com", "name": "Settings", "password": "a-long-password", "local_processing_consent": True})
    assert response.status_code == 201
    assert client.get("/api/auth/sessions").status_code == 200
    assert client.post("/api/auth/password", json={"current_password": "a-long-password", "new_password": "another-long-password"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"identifier": "settings_user", "password": "another-long-password"}).status_code == 200
