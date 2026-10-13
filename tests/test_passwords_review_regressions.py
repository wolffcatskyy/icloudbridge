"""Review regressions using disposable databases and HTTP response fixtures."""

import json
import logging
import sqlite3
from unittest.mock import AsyncMock

import httpx
import pytest

from icloudbridge.core.passwords_sync import PasswordsSyncEngine
from icloudbridge.sources.passwords.apple_csv import ApplePasswordsCSVParser
from icloudbridge.sources.passwords.diagnostics import log_failure, safe_failure
from icloudbridge.sources.passwords.models import PasswordEntry
from icloudbridge.sources.passwords.providers.nextcloud import NextcloudPasswordsProvider
from icloudbridge.sources.passwords.providers.vaultwarden import VaultwardenProvider
from icloudbridge.sources.passwords.retry import retry_addition
from icloudbridge.utils.db import PasswordsDB


def e(title="Example", username="", url=None, **kw):
    return PasswordEntry(title=title, username=username, url=url, password="fixture-only", **kw)


def remote(entries):
    p = AsyncMock()
    p.list_passwords.return_value = [
        {
            "title": x.title,
            "username": x.username,
            "password": x.password,
            "url": x.url,
            "notes": x.notes,
            "otp_auth": x.otp_auth,
            "extra_urls": x.extra_urls,
            "id": str(i),
        }
        for i, x in enumerate(entries)
    ]
    return p


async def test_three_repeated_syncs_keep_blank_username_and_url(tmp_path):
    entries = [
        e(),
        e("Google", "fixture", "https://accounts.google.invalid"),
        e("YouTube", "fixture", "https://accounts.google.invalid"),
    ]
    path = tmp_path / "apple.csv"
    ApplePasswordsCSVParser.write_file(entries, path)
    db = PasswordsDB(tmp_path / "db.sqlite")
    await db.initialize()
    for _ in range(3):
        result = await PasswordsSyncEngine(db).sync(apple_csv_path=path, provider=remote(entries))
        assert result["push"]["conflicts"] == []
        assert result["pull"]["new_entries"] == 0
    mappings = await db.get_all_password_mappings()
    assert len(mappings) == 3 and all(m["confirmed"] for m in mappings)
    assert (await db.get_last_sync("apple_import"))["entry_count"] == 3


async def test_legacy_null_duplicates_unconfirmed_until_seen_both(tmp_path):
    db = PasswordsDB(tmp_path / "db.sqlite")
    await db.initialize()
    with sqlite3.connect(db.db_path) as conn:
        conn.execute("ALTER TABLE password_mapping DROP COLUMN confirmed")
        for _ in range(2):
            conn.execute(
                "INSERT INTO password_mapping(title,url,username,provider_type,last_sync_timestamp,created_at) VALUES ('Example',NULL,'','asyncmock',1,1)"
            )
    await db.initialize()
    mappings = await db.get_all_password_mappings()
    assert len(mappings) == 1 and mappings[0]["confirmed"] == 0 and mappings[0]["url"] == ""
    path = tmp_path / "apple.csv"
    ApplePasswordsCSVParser.write_file([], path)
    result = await PasswordsSyncEngine(db).sync(
        apple_csv_path=path, provider=remote([e()]), output_apple_csv=tmp_path / "export.csv"
    )
    assert result["pull"]["new_entries"] == 1 and result["pull"]["conflicts"] == []


async def test_converged_rename_retires_old_tracking(tmp_path):
    db = PasswordsDB(tmp_path / "db.sqlite")
    await db.initialize()
    x = e("Old")
    await db.upsert_password_mapping(
        title=x.title,
        username=x.username,
        url=x.url,
        provider_id="0",
        provider_type="asyncmock",
        last_apple_hash=x.get_password_hash(),
        last_provider_hash=x.get_password_hash(),
    )
    path = tmp_path / "apple.csv"
    ApplePasswordsCSVParser.write_file([e("New")], path)
    result = await PasswordsSyncEngine(db).sync(apple_csv_path=path, provider=remote([e("New")]))
    assert result["push"]["conflicts"] == []
    assert [m["title"] for m in await db.get_all_password_mappings()] == ["New"]


def test_notes_and_otp_roundtrip(tmp_path):
    x = e(notes=" leading note\n", otp_auth="otpauth://totp/fixture?secret=ABC&issuer=test")
    path = tmp_path / "apple.csv"
    ApplePasswordsCSVParser.write_file([x], path)
    actual = ApplePasswordsCSVParser.parse_file(path)[0]
    assert actual.notes == x.notes
    assert PasswordsSyncEngine._otp(x.otp_auth) == PasswordsSyncEngine._otp("ABC")
    assert PasswordsSyncEngine._otp(x.otp_auth) != PasswordsSyncEngine._otp(
        x.otp_auth + "&digits=8"
    )


@pytest.mark.parametrize("encoded", [False, True])
async def test_nextcloud_returns_custom_fields(encoded):
    fields = [
        {"label": "Website 2", "value": "https://second.invalid", "type": "url"},
        {"label": "TOTP", "value": "ABC", "type": "secret"},
    ]
    p = NextcloudPasswordsProvider("https://fixture.invalid", "fixture", "throwaway")
    await p._client.aclose()
    p._client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json=[{"id": "x", "customFields": json.dumps(fields) if encoded else fields}]
            )
        )
    )
    rows = await p.list_passwords()
    assert rows[0]["otp_auth"] == "ABC" and rows[0]["extra_urls"] == ["https://second.invalid"]
    await p.close()


async def test_vaultwarden_batch_has_one_shared_push():
    p = VaultwardenProvider.__new__(VaultwardenProvider)
    p.client = AsyncMock()
    p.client.list_folders.return_value = []
    p.client.push_passwords.return_value = {"created": 200, "failed": 0}
    rows = [e(str(i)) for i in range(200)]
    result = await p.create_passwords(rows)
    assert result["created"] == 200
    p.client.push_passwords.assert_awaited_once()
    assert len(p.client.push_passwords.call_args.kwargs["entries"]) == 200


async def test_retry_rechecks_before_replaying(monkeypatch):
    monkeypatch.setattr("icloudbridge.sources.passwords.retry.asyncio.sleep", AsyncMock())
    request = httpx.Request("POST", "https://fixture.invalid")
    create = AsyncMock(side_effect=[httpx.ReadTimeout("secret", request=request), None])
    exists = AsyncMock(return_value=True)
    assert not await retry_addition(create, exists)
    create.assert_awaited_once()
    exists.assert_awaited_once()


async def test_retry_429_then_success(monkeypatch):
    monkeypatch.setattr("icloudbridge.sources.passwords.retry.asyncio.sleep", AsyncMock())
    response = httpx.Response(429, request=httpx.Request("POST", "https://fixture.invalid"))
    create = AsyncMock(
        side_effect=[
            httpx.HTTPStatusError("secret", request=response.request, response=response),
            None,
        ]
    )
    assert await retry_addition(create, AsyncMock(return_value=False))
    assert create.await_count == 2


def test_diagnostics_do_not_log_exception_secret(caplog):
    try:
        raise FileExistsError("sensitive-fixture-password")
    except Exception as exc:
        with caplog.at_level(logging.ERROR):
            log_failure(logging.getLogger("test"), exc)
        assert "choose a new" in safe_failure(exc)
    assert "sensitive-fixture-password" not in caplog.text
    assert "test_diagnostics_do_not_log_exception_secret" in caplog.text


async def test_missing_password_is_reviewed_not_added(tmp_path):
    x = PasswordEntry(title="Passkey fixture", username="", password="")
    path = tmp_path / "apple.csv"
    ApplePasswordsCSVParser.write_file([x], path)
    db = AsyncMock()
    db.get_all_password_mappings.return_value = []
    p = remote([])
    result = await PasswordsSyncEngine(db).sync(apple_csv_path=path, provider=p, simulate=True)
    assert result["push"]["planned_created"] == 0
    assert result["push"]["conflicts"][0]["reason"] == "missing_password"
    db.confirm_password_snapshot.assert_not_awaited()


async def test_both_deleted_only_removes_tracking(tmp_path):
    db = PasswordsDB(tmp_path / "db.sqlite")
    await db.initialize()
    x = e()
    await db.upsert_password_mapping(
        title=x.title,
        username=x.username,
        url=x.url,
        provider_id="0",
        provider_type="asyncmock",
        last_apple_hash=x.get_password_hash(),
        last_provider_hash=x.get_password_hash(),
    )
    path = tmp_path / "apple.csv"
    ApplePasswordsCSVParser.write_file([], path)
    p = remote([])
    result = await PasswordsSyncEngine(db).sync(apple_csv_path=path, provider=p)
    assert not await db.get_all_password_mappings()
    assert not result["push"]["conflicts"]
    p.delete_password.assert_not_awaited()


async def test_failed_retry_read_never_replays_post(monkeypatch):
    monkeypatch.setattr("icloudbridge.sources.passwords.retry.asyncio.sleep", AsyncMock())
    create = AsyncMock(side_effect=httpx.ReadTimeout("fixture"))
    with pytest.raises(RuntimeError):
        await retry_addition(create, AsyncMock(side_effect=RuntimeError("read failed")))
    create.assert_awaited_once()


async def test_one_sided_old_identity_stays_held_after_new_pair_matches(tmp_path):
    db = PasswordsDB(tmp_path / "db.sqlite")
    await db.initialize()
    x = e("Old")
    await db.upsert_password_mapping(
        title=x.title,
        username=x.username,
        url=x.url,
        provider_id="0",
        provider_type="asyncmock",
        last_apple_hash=x.get_password_hash(),
        last_provider_hash=x.get_password_hash(),
    )
    path = tmp_path / "apple.csv"
    ApplePasswordsCSVParser.write_file([x, e("New")], path)
    p = remote([e("New")])
    for _ in range(2):
        result = await PasswordsSyncEngine(db).sync(apple_csv_path=path, provider=p)
        assert result["push"]["created"] == 0
        assert result["push"]["conflicts"][0]["reason"] == "missing_side_review"
    p.create_password.assert_not_awaited()
    assert len(await db.get_all_password_mappings()) == 2
