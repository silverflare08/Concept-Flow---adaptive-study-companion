"""Account tests use temporary storage, never the user's study files."""
import pytest
from studybuddy.auth import AuthStore


def test_password_and_session_lifecycle(tmp_path):
    store = AuthStore(tmp_path / "auth.db")
    user = store.signup("alice", "alice@example.com", "Alice", "a-long-password")
    assert "password_hash" not in user
    assert user["preferences"]["theme"] == "neutral"
    assert store.login("ALICE", "a-long-password")["id"] == user["id"]
    with pytest.raises(ValueError):
        store.login("alice", "incorrect-password")
    token = store.create_session(user["id"])
    identity = store.authenticate(token)
    assert identity["user"]["id"] == user["id"]
    store.revoke(user["id"], identity["session_id"])
    assert store.authenticate(token) is None


def test_account_uniqueness_and_session_ownership(tmp_path):
    store = AuthStore(tmp_path / "auth.db")
    alice = store.signup("alice", "alice@example.com", "Alice", "a-long-password")
    bob = store.signup("bob", "bob@example.com", "Bob", "b-long-password")
    with pytest.raises(ValueError):
        store.signup("ALICE", "other@example.com", "Other", "a-long-password")
    token = store.create_session(alice["id"])
    session = store.authenticate(token)
    store.revoke(bob["id"], session["session_id"])
    assert store.authenticate(token) is not None
    store.change_password(alice["id"], "a-long-password", "new-long-password")
    assert store.authenticate(token) is None
    assert store.login("alice", "new-long-password")["id"] == alice["id"]


def test_username_matches_form_rules(tmp_path):
    store = AuthStore(tmp_path / "auth.db")
    user = store.signup(" Palak.Mittal ", "palak@example.com", "Palak Mittal", "a-long-password")
    assert user["username"] == "palak.mittal"
    assert store.login("PALAK.MITTAL", "a-long-password")["id"] == user["id"]
    with pytest.raises(ValueError, match="No spaces"):
        store.signup("palak mittal", "other@example.com", "Palak", "a-long-password")
