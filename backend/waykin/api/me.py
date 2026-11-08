"""Accounts, sessions, families, invites and the family stream. Everything is under /api/me.

The session cookie is set with Path=/api/me, so browsers never send it to /api/routes or /api/routes/reroute:
the server still cannot link a route request to a person (spec B5). No endpoint here takes or stores a location;
/demo-people only reads the fixed, made-up spots of the demo family.
A family member who isn't one gets 404, never 403, so family ids can't be probed.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request, Response, WebSocket, WebSocketDisconnect

from waykin import constants as C
from waykin import schemas as S
from waykin.accounts.hub import FamilyHub, FamilyJourney
from waykin.accounts.security import RateLimiter
from waykin.accounts.store import Account, AccountStore, StoreError
from waykin.api.deps import api_error, get_state
from waykin.demo import people as demo_family

router = APIRouter(prefix="/me")
COOKIE, COOKIE_PATH = "wk_session", "/api/me"
_PING_S = 20.0


# ------------------------------------------------------------ dependencies
def ensure_accounts(state) -> AccountStore:
    """Real mode creates the store at startup; tests that build their own AppState get an in-memory one."""
    if state.accounts is None:
        state.accounts = AccountStore(":memory:")
    if state.family_hub is None:
        state.family_hub = FamilyHub()
    if not hasattr(state.accounts, "login_limiter"):
        state.accounts.login_limiter = RateLimiter(C.LOGIN_ATTEMPTS_PER_MIN)
    return state.accounts


def store(state=Depends(get_state)) -> AccountStore:
    return ensure_accounts(state)


def current(request: Request, accounts: AccountStore = Depends(store)) -> Account:
    me = accounts.session_account(request.cookies.get(COOKIE))
    if me is None:
        raise api_error(401, "invalid_token", "please log in")
    return me


def _err(e: StoreError):
    return api_error(e.status, e.code, str(e))


def _member_or_404(accounts: AccountStore, fid: str, me: Account):
    fam = accounts.family(fid)
    if fam is None or not accounts.is_member(fid, me.id):
        raise api_error(404, "not_found", "unknown family")
    return fam


def _set_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(COOKIE, token, max_age=C.SESSION_TTL_DAYS * 86400, path=COOKIE_PATH, httponly=True,
                        samesite="strict", secure=request.url.scheme == "https")


def _account_out(a: Account) -> S.AccountOut:
    return S.AccountOut(account_id=a.id, display_name=a.display_name, login=a.login, public_key=a.public_key)


def _detail(accounts: AccountStore, hub: FamilyHub, fid: str, me: Account) -> S.FamilyDetail:
    fam = accounts.family(fid)
    members = accounts.members(fid)
    mine = next((m for m in members if m["id"] == me.id), None)
    return S.FamilyDetail(
        family_id=fid, name=fam["name"], owner_id=fam["owner_id"], key_version=fam["key_version"],
        my_wrapped_key=mine["wrapped_key"] if mine else None, my_key_version=mine["key_version"] if mine else None,
        members=[S.FamilyMember(account_id=m["id"], display_name=m["display_name"], public_key=m["public_key"],
                                is_owner=m["id"] == fam["owner_id"]) for m in members],
        journeys=[S.FamilyJourneyOut(**j) for j in hub.active_for(fid)],
    )


# ------------------------------------------------------------ account and session
@router.post("/account", response_model=S.AccountOut, status_code=201)
def sign_up(body: S.SignUp, request: Request, response: Response, accounts: AccountStore = Depends(store)):
    ip = request.client.host if request.client else "?"
    if not accounts.login_limiter.allow(f"signup:{ip}"):
        raise api_error(429, "rate_limited", "too many attempts; wait a minute")
    try:
        a = accounts.create_account(body.login, body.display_name, body.password)
    except StoreError as e:
        raise _err(e) from None
    _set_cookie(response, request, accounts.new_session(a.id))
    return _account_out(a)


@router.post("/session", response_model=S.AccountOut)
def log_in(body: S.LogIn, request: Request, response: Response, accounts: AccountStore = Depends(store)):
    ip = request.client.host if request.client else "?"
    if not accounts.login_limiter.allow(f"login-ip:{ip}", f"login:{body.login.strip().lower()}"):
        raise api_error(429, "rate_limited", "too many attempts; wait a minute")
    a = accounts.check_login(body.login, body.password)
    if a is None:
        raise api_error(401, "invalid_token", "wrong login or password")   # same message for both cases
    _set_cookie(response, request, accounts.new_session(a.id))
    return _account_out(a)


@router.delete("/session", status_code=204)
def log_out(request: Request, accounts: AccountStore = Depends(store)) -> Response:
    accounts.end_session(request.cookies.get(COOKIE))
    r = Response(status_code=204)
    r.delete_cookie(COOKIE, path=COOKIE_PATH)
    return r


@router.get("/account", response_model=S.AccountOut)
def who_am_i(me: Account = Depends(current)):
    return _account_out(me)


@router.get("/demo-people", response_model=S.DemoPeople)
def demo_people(me: Account = Depends(current), state=Depends(get_state)) -> S.DemoPeople:
    """Fixed, made-up spots from waykin/demo/people.json, for the demo account only; everyone else gets []."""
    if not state.settings.DEMO_MODE:
        return S.DemoPeople(people=[])
    return S.DemoPeople(people=demo_family.people_for(ensure_accounts(state), me))


def _not_the_demo_account(state, me: Account) -> None:
    """The demo login is shared by everyone trying the published demo, so nobody can break it for the rest."""
    if state.settings.DEMO_MODE and demo_family.is_presenter(me):
        raise api_error(403, "forbidden", "the demo account can't do this")


@router.put("/account/public-key", status_code=204)
def set_public_key(body: S.PublicKeyIn, me: Account = Depends(current), accounts: AccountStore = Depends(store)):
    accounts.set_public_key(me.id, body.public_key)
    return Response(status_code=204)


@router.delete("/account", status_code=204)
async def delete_account(request: Request, me: Account = Depends(current), state=Depends(get_state)) -> Response:
    _not_the_demo_account(state, me)
    accounts = ensure_accounts(state)
    for fid in accounts.delete_account(me.id):
        state.family_hub.drop_walker(fid, me.id)
        await state.family_hub.publish(accounts.member_ids(fid), {"type": "member.left", "family_id": fid,
                                                                   "account_id": me.id})
    r = Response(status_code=204)
    r.delete_cookie(COOKIE, path=COOKIE_PATH)
    return r


# ------------------------------------------------------------ families
@router.get("/families", response_model=list[S.FamilySummary])
def my_families(me: Account = Depends(current), accounts: AccountStore = Depends(store)):
    return [S.FamilySummary(family_id=f["id"], name=f["name"], n_members=f["n_members"], is_owner=f["owner_id"] == me.id)
            for f in accounts.families_of(me.id)]


@router.post("/families", response_model=S.FamilyDetail, status_code=201)
def create_family(body: S.FamilyCreate, me: Account = Depends(current), state=Depends(get_state)):
    accounts = ensure_accounts(state)
    if len(accounts.families_of(me.id)) >= 5:
        raise api_error(409, "validation", "you can be in at most 5 families")
    fid = accounts.create_family(me.id, body.name, body.wrapped_key)
    return _detail(accounts, state.family_hub, fid, me)


@router.get("/families/{fid}", response_model=S.FamilyDetail)
def family_detail(fid: str, me: Account = Depends(current), state=Depends(get_state)):
    accounts = ensure_accounts(state)
    _member_or_404(accounts, fid, me)
    return _detail(accounts, state.family_hub, fid, me)


@router.post("/families/{fid}/invites", response_model=S.InviteCreated, status_code=201)
def create_invite(fid: str, me: Account = Depends(current), accounts: AccountStore = Depends(store)):
    _member_or_404(accounts, fid, me)
    token, expires = accounts.create_invite(fid, me.id)
    return S.InviteCreated(invite_token=token, expires_at=expires)


@router.post("/families/{fid}/invite-preview", response_model=S.InvitePreview)
def invite_preview(fid: str, body: S.InviteToken, me: Account = Depends(current),
                   accounts: AccountStore = Depends(store)):
    try:
        name, by = accounts.invite_preview(fid, body.invite_token)
    except StoreError as e:
        raise _err(e) from None
    return S.InvitePreview(family_name=name, invited_by=by)


@router.post("/families/{fid}/join", response_model=S.FamilyDetail)
async def join_family(fid: str, body: S.JoinFamily, me: Account = Depends(current), state=Depends(get_state)):
    accounts = ensure_accounts(state)
    try:
        accounts.join(fid, me.id, body.invite_token, body.wrapped_key, body.key_version)
    except StoreError as e:
        raise _err(e) from None
    await state.family_hub.publish(accounts.member_ids(fid), {"type": "member.joined", "family_id": fid,
                                                              "account_id": me.id, "display_name": me.display_name})
    return _detail(accounts, state.family_hub, fid, me)


@router.delete("/families/{fid}/members/{aid}", status_code=204)
async def remove_member(fid: str, aid: str, me: Account = Depends(current), state=Depends(get_state)) -> Response:
    _not_the_demo_account(state, me)
    accounts = ensure_accounts(state)
    fam = _member_or_404(accounts, fid, me)
    if aid != me.id and fam["owner_id"] != me.id:
        raise api_error(403, "forbidden", "only the family owner can remove someone else")
    if not accounts.is_member(fid, aid):
        raise api_error(404, "not_found", "not a member")
    before = accounts.member_ids(fid)
    accounts.remove_member(fid, aid)
    for jid in state.family_hub.drop_walker(fid, aid):
        await state.family_hub.publish(before, {"type": "journey.ended", "family_id": fid, "journey_id": jid,
                                                "reason": "stopped"})
    await state.family_hub.publish(before, {"type": "member.left", "family_id": fid, "account_id": aid})
    return Response(status_code=204)


@router.put("/families/{fid}/keys", status_code=204)
async def rotate_keys(fid: str, body: S.KeyRotation, me: Account = Depends(current), state=Depends(get_state)):
    accounts = ensure_accounts(state)
    fam = _member_or_404(accounts, fid, me)
    if fam["owner_id"] != me.id:
        raise api_error(403, "forbidden", "only the family owner can replace the family key")
    try:
        accounts.rotate_key(fid, body.key_version, body.wrapped)
    except StoreError as e:
        raise _err(e) from None
    await state.family_hub.publish(accounts.member_ids(fid), {"type": "family.key_rotated", "family_id": fid,
                                                              "key_version": body.key_version})
    return Response(status_code=204)


# ------------------------------------------------------------ family journeys
@router.post("/families/{fid}/journeys", response_model=S.JourneyCreated, status_code=201)
async def start_family_journey(fid: str, body: S.FamilyJourneyCreate, me: Account = Depends(current),
                               state=Depends(get_state)):
    """A journey the whole family can follow. The location stream is the normal end-to-end encrypted relay; the
    family only receives the journey key wrapped with the family key, which the server cannot open."""
    accounts = ensure_accounts(state)
    fam = _member_or_404(accounts, fid, me)
    if body.key_version != fam["key_version"]:
        raise api_error(409, "validation", "the family key has changed; reload the family first")
    j, walker, viewer = state.journeys.create(body.expires_in_min)
    fj = FamilyJourney(journey_id=j.journey_id, family_id=fid, walker_id=me.id, walker_display_name=me.display_name,
                       viewer_token=viewer, wrapped_journey_key=body.wrapped_journey_key,
                       key_version=body.key_version, expires_at=j.expires_at.isoformat())
    event = state.family_hub.start(fj)
    event["family_id"] = fid
    await state.family_hub.publish(accounts.member_ids(fid), event)
    return S.JourneyCreated(journey_id=j.journey_id, walker_token=walker, viewer_token=viewer,
                            expires_at=j.expires_at, relay_mode=state.settings.relay_mode)


# ------------------------------------------------------------ family stream
def _origin_ok(ws: WebSocket, settings) -> bool:
    origin = ws.headers.get("origin")
    if origin is None:
        return True   # non-browser clients (tests, CLI). Browsers always send Origin on WebSockets.
    host = ws.headers.get("host", "")
    return origin in settings.cors_origins or origin.split("://", 1)[-1] == host


@router.websocket("/stream")
async def family_stream(ws: WebSocket) -> None:
    state = ws.app.state.waykin
    accounts = ensure_accounts(state)
    me = accounts.session_account(ws.cookies.get(COOKIE))
    if me is None or not _origin_ok(ws, state.settings):
        await ws.close(code=4401)
        return
    await ws.accept()
    hub: FamilyHub = state.family_hub
    hub.add(me.id, ws)
    try:
        await ws.send_text(json.dumps({"type": "ready"}))
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=_PING_S)
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(me.id, ws)


async def announce_end(state, journey_id: str, reason: str) -> None:
    """Relay end hook: tell the family a walk finished."""
    if state.family_hub is None:
        return
    fid, event = state.family_hub.end(journey_id, reason)
    if fid is not None and state.accounts is not None:
        await state.family_hub.publish(state.accounts.member_ids(fid), event)
