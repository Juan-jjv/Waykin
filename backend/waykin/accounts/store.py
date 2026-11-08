"""SQLite store for accounts, sessions, families, members and invites.

Never stores a location, a route, a journey or a raw family key. Family keys are kept only *wrapped*: encrypted
in the browser to each member's public key, so the server holds opaque blobs it cannot open. Tokens (sessions,
invites) are stored only as sha256 hashes.
"""
from __future__ import annotations

import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from waykin import constants as C
from waykin.accounts.security import check_password, hash_password, new_token, token_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY, login TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
  pw_salt BLOB NOT NULL, pw_hash BLOB NOT NULL, public_key TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash BLOB PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS families (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, owner_id TEXT NOT NULL, key_version INTEGER NOT NULL,
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS members (
  family_id TEXT NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  wrapped_key TEXT, key_version INTEGER, joined_at TEXT NOT NULL,
  PRIMARY KEY (family_id, account_id));
CREATE TABLE IF NOT EXISTS invites (
  token_hash BLOB PRIMARY KEY, family_id TEXT NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  created_by TEXT NOT NULL, expires_at TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0);
"""


class StoreError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code = status, code


@dataclass
class Account:
    id: str
    login: str
    display_name: str
    public_key: str | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t: datetime) -> str:
    return t.isoformat()


class AccountStore:
    def __init__(self, path: str = ":memory:"):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._db.execute("PRAGMA foreign_keys = ON")
            self._db.executescript(SCHEMA)

    def _q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    # ------------------------------------------------------------ accounts and sessions
    def create_account(self, login: str, display_name: str, password: str) -> Account:
        login = login.strip().lower()
        salt, pw = hash_password(password)
        aid = secrets.token_urlsafe(9)
        try:
            self._q("INSERT INTO accounts VALUES (?,?,?,?,?,NULL,?)",
                    (aid, login, display_name.strip(), salt, pw, _iso(_now())))
        except sqlite3.IntegrityError:
            raise StoreError(409, "validation", "that login is already taken") from None
        return Account(aid, login, display_name.strip(), None)

    def check_login(self, login: str, password: str) -> Account | None:
        rows = self._q("SELECT * FROM accounts WHERE login = ?", (login.strip().lower(),))
        if not rows:
            from waykin.accounts.security import burn_time
            burn_time(password)
            return None
        r = rows[0]
        if not check_password(password, r["pw_salt"], r["pw_hash"]):
            return None
        return Account(r["id"], r["login"], r["display_name"], r["public_key"])

    def get_account(self, aid: str) -> Account | None:
        rows = self._q("SELECT id, login, display_name, public_key FROM accounts WHERE id = ?", (aid,))
        return Account(*rows[0]) if rows else None

    def set_public_key(self, aid: str, public_key: str) -> None:
        self._q("UPDATE accounts SET public_key = ? WHERE id = ?", (public_key, aid))

    def delete_account(self, aid: str) -> list[str]:
        """Delete the account, its sessions and memberships. Owned families pass to the longest-standing member,
        or are deleted when nobody is left. Returns the ids of families it belonged to."""
        with self._lock:
            fids = [r["family_id"] for r in self._q("SELECT family_id FROM members WHERE account_id = ?", (aid,))]
            for fid in fids:
                self.remove_member(fid, aid)
            self._q("DELETE FROM accounts WHERE id = ?", (aid,))
        return fids

    def new_session(self, aid: str) -> str:
        token = new_token()
        self._q("INSERT INTO sessions VALUES (?,?,?)",
                (token_hash(token), aid, _iso(_now() + timedelta(days=C.SESSION_TTL_DAYS))))
        return token

    def session_account(self, token: str | None) -> Account | None:
        if not token:
            return None
        rows = self._q("SELECT account_id, expires_at FROM sessions WHERE token_hash = ?", (token_hash(token),))
        if not rows or datetime.fromisoformat(rows[0]["expires_at"]) <= _now():
            return None
        return self.get_account(rows[0]["account_id"])

    def end_session(self, token: str | None) -> None:
        if token:
            self._q("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))

    # ------------------------------------------------------------ families
    def create_family(self, owner: str, name: str, wrapped_key: str) -> str:
        fid = secrets.token_urlsafe(9)
        with self._lock:
            self._q("INSERT INTO families VALUES (?,?,?,1,?)", (fid, name.strip(), owner, _iso(_now())))
            self._q("INSERT INTO members VALUES (?,?,?,1,?)", (fid, owner, wrapped_key, _iso(_now())))
        return fid

    def is_member(self, fid: str, aid: str) -> bool:
        return bool(self._q("SELECT 1 FROM members WHERE family_id = ? AND account_id = ?", (fid, aid)))

    def family(self, fid: str) -> sqlite3.Row | None:
        rows = self._q("SELECT * FROM families WHERE id = ?", (fid,))
        return rows[0] if rows else None

    def families_of(self, aid: str) -> list[sqlite3.Row]:
        return self._q("""SELECT f.*, (SELECT COUNT(*) FROM members m2 WHERE m2.family_id = f.id) AS n_members
                          FROM families f JOIN members m ON m.family_id = f.id WHERE m.account_id = ?
                          ORDER BY f.created_at""", (aid,))

    def members(self, fid: str) -> list[sqlite3.Row]:
        return self._q("""SELECT a.id, a.display_name, a.public_key, m.wrapped_key, m.key_version, m.joined_at
                          FROM members m JOIN accounts a ON a.id = m.account_id
                          WHERE m.family_id = ? ORDER BY m.joined_at""", (fid,))

    def member_ids(self, fid: str) -> list[str]:
        return [r["account_id"] for r in self._q("SELECT account_id FROM members WHERE family_id = ?", (fid,))]

    def create_invite(self, fid: str, aid: str) -> tuple[str, datetime]:
        token = new_token()
        expires = _now() + timedelta(hours=C.INVITE_TTL_H)
        self._q("INSERT INTO invites VALUES (?,?,?,?,0)", (token_hash(token), fid, aid, _iso(expires)))
        return token, expires

    def _live_invite(self, fid: str, token: str) -> sqlite3.Row:
        rows = self._q("SELECT * FROM invites WHERE token_hash = ? AND family_id = ?", (token_hash(token), fid))
        if not rows or rows[0]["used"] or datetime.fromisoformat(rows[0]["expires_at"]) <= _now():
            raise StoreError(404, "not_found", "this invite link is invalid or has expired")
        return rows[0]

    def invite_preview(self, fid: str, token: str) -> tuple[str, str]:
        inv = self._live_invite(fid, token)
        fam = self.family(fid)
        inviter = self.get_account(inv["created_by"])
        return fam["name"], inviter.display_name if inviter else "A family member"

    def join(self, fid: str, aid: str, token: str, wrapped_key: str, key_version: int) -> None:
        with self._lock:
            inv = self._live_invite(fid, token)
            fam = self.family(fid)
            if self.is_member(fid, aid):
                raise StoreError(409, "validation", "you are already in this family")
            if len(self.member_ids(fid)) >= C.FAMILY_MAX_MEMBERS:
                raise StoreError(409, "validation", f"a family can have at most {C.FAMILY_MAX_MEMBERS} members")
            if key_version != fam["key_version"]:
                raise StoreError(409, "validation", "this invite link is out of date; ask for a new one")
            self._q("UPDATE invites SET used = 1 WHERE token_hash = ?", (inv["token_hash"],))
            self._q("INSERT INTO members VALUES (?,?,?,?,?)", (fid, aid, wrapped_key, key_version, _iso(_now())))

    def remove_member(self, fid: str, aid: str) -> None:
        with self._lock:
            fam = self.family(fid)
            if fam is None:
                return
            self._q("DELETE FROM members WHERE family_id = ? AND account_id = ?", (fid, aid))
            left = self._q("SELECT account_id FROM members WHERE family_id = ? ORDER BY joined_at", (fid,))
            if not left:
                self._q("DELETE FROM families WHERE id = ?", (fid,))
            elif fam["owner_id"] == aid:
                self._q("UPDATE families SET owner_id = ? WHERE id = ?", (left[0]["account_id"], fid))

    def rotate_key(self, fid: str, key_version: int, wrapped: dict[str, str]) -> None:
        """Replace every member's wrapped key with a new version. Outstanding invites carry the old key: drop them."""
        with self._lock:
            fam = self.family(fid)
            if key_version != fam["key_version"] + 1:
                raise StoreError(409, "validation", "key_version must be the current version + 1")
            if set(wrapped) != set(self.member_ids(fid)):
                raise StoreError(422, "validation", "wrapped keys must cover exactly the current members")
            for aid, w in wrapped.items():
                self._q("UPDATE members SET wrapped_key = ?, key_version = ? WHERE family_id = ? AND account_id = ?",
                        (w, key_version, fid, aid))
            self._q("UPDATE families SET key_version = ? WHERE id = ?", (key_version, fid))
            self._q("DELETE FROM invites WHERE family_id = ?", (fid,))

    def set_wrapped_key(self, fid: str, aid: str, wrapped: str, key_version: int) -> None:
        self._q("UPDATE members SET wrapped_key = ?, key_version = ? WHERE family_id = ? AND account_id = ?",
                (wrapped, key_version, fid, aid))
