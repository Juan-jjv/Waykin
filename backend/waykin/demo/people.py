"""The demo account and its family (DEMO_MODE only), created at startup so a fresh deploy has them.

`people.json` holds made-up people at fixed spots across Edmonton. Only the presenter account is ever sent those
spots (GET /api/me/demo-people); every other account gets an empty list. The people never sign in on a device:
their public keys have no private half anywhere, so they exist only so "Reset family key" can cover every member.
"""
from __future__ import annotations

import json
from pathlib import Path

from waykin import schemas as S
from waykin.accounts.store import Account, AccountStore

PEOPLE_PATH = Path(__file__).resolve().parent / "people.json"


def load() -> dict:
    return json.loads(PEOPLE_PATH.read_text())


def _account(store: AccountStore, login: str, name: str, password: str) -> Account:
    rows = store._q("SELECT id FROM accounts WHERE login = ?", (login,))
    return store.get_account(rows[0]["id"]) if rows else store.create_account(login, name, password)


def _family_id(store: AccountStore, presenter: Account, name: str) -> str | None:
    return next((f["id"] for f in store.families_of(presenter.id) if f["name"] == name), None)


def seed(store: AccountStore, password: str) -> None:
    """Create whatever is missing: the presenter, the people, the family and the memberships."""
    cfg = load()
    presenter = _account(store, cfg["presenter"]["login"], cfg["presenter"]["display_name"], password)
    fid = _family_id(store, presenter, cfg["family_name"]) or store.create_family(presenter.id, cfg["family_name"], None)
    for p in cfg["people"]:
        person = _account(store, p["login"], p["display_name"], password)
        if person.public_key != p["public_key"]:
            store.set_public_key(person.id, p["public_key"])
        if not store.is_member(fid, person.id):
            token, _ = store.create_invite(fid, presenter.id)
            store.join(fid, person.id, token, None, store.family(fid)["key_version"])


def is_presenter(me: Account) -> bool:
    return me.login == load()["presenter"]["login"]


def people_for(store: AccountStore, me: Account) -> list[S.DemoPerson]:
    cfg = load()
    if me.login != cfg["presenter"]["login"]:
        return []
    fid = _family_id(store, me, cfg["family_name"])
    out = []
    for p in cfg["people"]:
        rows = store._q("SELECT id FROM accounts WHERE login = ?", (p["login"],))
        if fid is None or not rows or not store.is_member(fid, rows[0]["id"]):
            continue
        out.append(S.DemoPerson(account_id=rows[0]["id"], display_name=p["display_name"], family_id=fid,
                                position=S.LatLon(**p["position"]), near=p["near"]))
    return out
