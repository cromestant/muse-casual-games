"""muse-games relay API (v0: dumb pipe over HTTP).

Exposes the Redis relay keyspace as JSON/HTTP so players don't need Redis
or SSH access. Listens on 127.0.0.1:8001; nginx terminates TLS at
https://relay.onthe1.app and reverse-proxies here.

Auth: every mutating call carries {handle, secret}. The secret is registered
once via /v0/players/register and stored as a sha256 hash at
mg:player:<handle> (same keyspace as PROTOCOL.md). v0 trusts players and
verifies afterwards: the API checks identity (handle owns the seat) but does
NOT validate game rules — clients validate moves with the game logic before
sending, exactly like the Redis path.

Run: uvicorn api:app --host 127.0.0.1 --port 8001
"""

import hashlib
import hmac
import secrets
import time

import redis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

r = redis.Redis(host="127.0.0.1", port=6379, db=5, decode_responses=True)

app = FastAPI(title="muse-games relay", version="0.1.0")

# Board widgets poll the public read endpoints from the player's browser.
# Reads are public data (rooms, move logs, lobby); all mutating calls still
# need the handle secret, which never goes into widget HTML.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ---------- models ----------

class Authed(BaseModel):
    handle: str
    secret: str


class Register(Authed):
    pass


class CreateRoom(Authed):
    game: str
    version_sha: str
    seats: list[str]          # ordered handles; index == seat number
    config: dict = {}


class PostMove(Authed):
    seat: int
    type: str
    payload: dict


class PostCommit(Authed):
    commitment: str           # hex sha256 (commit-reveal games)


# ---------- helpers ----------

def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def check_auth(handle: str, secret: str) -> None:
    stored = r.hget(f"mg:player:{handle}", "secret_hash")
    if not stored or not hmac.compare_digest(stored, _hash(secret)):
        raise HTTPException(status_code=401, detail="bad handle or secret")


def room_or_404(code: str) -> dict:
    room = r.hgetall(f"mg:room:{code}")
    if not room:
        raise HTTPException(status_code=404, detail="unknown room")
    return room


def seat_of(room: dict, handle: str) -> int:
    import json
    seats = json.loads(room["seats"])
    if handle not in seats:
        raise HTTPException(status_code=403, detail="handle is not a seat in this room")
    return seats.index(handle)


def new_code() -> str:
    import random
    import string
    alpha = string.ascii_uppercase + string.digits
    for _ in range(20):
        code = "".join(random.choice(alpha) for _ in range(4)) + "-" + \
               "".join(random.choice(alpha) for _ in range(4))
        if not r.sismember("mg:rooms", code):
            return code
    raise HTTPException(status_code=500, detail="could not allocate room code")


# ---------- meta ----------

@app.get("/health")
def health():
    r.ping()
    return {"ok": True}


# ---------- players ----------

@app.post("/v0/players/register")
def register(p: Register):
    key = f"mg:player:{p.handle}"
    stored = r.hget(key, "secret_hash")
    if stored:
        if hmac.compare_digest(stored, _hash(p.secret)):
            return {"handle": p.handle, "status": "already_registered"}
        raise HTTPException(status_code=409, detail="handle taken")
    r.hset(key, mapping={"secret_hash": _hash(p.secret), "created_ts": int(time.time())})
    return {"handle": p.handle, "status": "registered"}


# ---------- rooms ----------

@app.post("/v0/rooms")
def create_room(p: CreateRoom):
    check_auth(p.handle, p.secret)
    if p.handle not in p.seats:
        raise HTTPException(status_code=400, detail="creator must occupy a seat")
    import json
    code = new_code()
    r.hset(f"mg:room:{code}", mapping={
        "game": p.game,
        "version_sha": p.version_sha,
        "seats": json.dumps(p.seats),
        "status": "open" if len(p.seats) > 1 else "active",
        "config": json.dumps(p.config),
        "created_ts": int(time.time()),
    })
    r.sadd("mg:rooms", code)
    return {"code": code}


@app.get("/v0/rooms/{code}")
def get_room(code: str):
    import json
    room = room_or_404(code)
    room["seats"] = json.loads(room["seats"])
    room["config"] = json.loads(room["config"])
    return room


@app.post("/v0/rooms/{code}/finish")
def finish_room(code: str, p: Authed):
    check_auth(p.handle, p.secret)
    room = room_or_404(code)
    seat_of(room, p.handle)  # must be a player in the room
    r.hset(f"mg:room:{code}", "status", "finished")
    return {"code": code, "status": "finished"}


# ---------- moves (the log) ----------

@app.post("/v0/rooms/{code}/moves")
def post_move(code: str, p: PostMove):
    check_auth(p.handle, p.secret)
    room = room_or_404(code)
    if p.seat != seat_of(room, p.handle):
        raise HTTPException(status_code=403, detail="seat does not belong to handle")
    import json
    envelope = {
        "seat": p.seat,
        "handle": p.handle,
        "type": p.type,
        "payload": p.payload,
        "ts": int(time.time()),
    }
    seq = r.rpush(f"mg:room:{code}:moves", json.dumps(envelope, separators=(",", ":")))
    if room["status"] == "open":
        r.hset(f"mg:room:{code}", "status", "active")
    return {"seq": seq}


@app.get("/v0/rooms/{code}/moves")
def get_moves(code: str, since: int = 0):
    room_or_404(code)
    import json
    raw = r.lrange(f"mg:room:{code}:moves", since, -1)
    return {"moves": [json.loads(x) for x in raw], "since": since}


# ---------- commits (commit-reveal games) ----------

@app.post("/v0/rooms/{code}/commits")
def post_commit(code: str, p: PostCommit):
    check_auth(p.handle, p.secret)
    room = room_or_404(code)
    seat = seat_of(room, p.handle)
    r.hset(f"mg:room:{code}:commits", str(seat), p.commitment)
    return {"seat": seat, "status": "committed"}


@app.get("/v0/rooms/{code}/commits")
def get_commits(code: str):
    room_or_404(code)
    return r.hgetall(f"mg:room:{code}:commits")


# ---------- lobby ----------

@app.post("/v0/lobby/{game}/join")
def lobby_join(game: str, p: Authed):
    check_auth(p.handle, p.secret)
    import json
    r.rpush(f"mg:lobby:{game}", json.dumps({"handle": p.handle, "since_ts": int(time.time())}))
    return {"game": game, "status": "waiting"}


@app.get("/v0/lobby/{game}")
def lobby_list(game: str):
    import json
    return {"game": game,
            "waiting": [json.loads(x) for x in r.lrange(f"mg:lobby:{game}", 0, -1)]}


@app.post("/v0/lobby/{game}/leave")
def lobby_leave(game: str, p: Authed):
    check_auth(p.handle, p.secret)
    import json
    entries = r.lrange(f"mg:lobby:{game}", 0, -1)
    removed = 0
    for e in entries:
        if json.loads(e)["handle"] == p.handle:
            r.lrem(f"mg:lobby:{game}", 1, e)
            removed += 1
    return {"game": game, "removed": removed}


# ---------- code distribution ----------
#
# The relay also serves the game code itself, so a player agent can fetch
# exactly the version a room pins without touching github.com:
#   GET /v0/code/versions            -> {"versions": ["v0.1.0", ...]}
#   GET /v0/code/{version}/games     -> [{slug, manifest}, ...]
#   GET /v0/code/{version}/{path}    -> raw file bytes at that tag/commit
# Served from a local clone of the public repo via `git show` (no working
# tree involved). GitHub remains the source of truth: push and sign tags
# there; the clone lazy-fetches on a cache miss.

CODE_DIR = "/var/www/relay.onthe1.app/code"


def _git_bytes(*args: str):
    import subprocess
    return subprocess.run(["git", "-C", CODE_DIR, *args],
                          capture_output=True, timeout=25)


def _tags() -> list:
    p = _git_bytes("tag", "--list")
    return p.stdout.decode().split() if p.returncode == 0 else []


def resolve_version(v: str) -> str:
    import re
    if v in _tags():
        return v
    if re.fullmatch(r"[0-9a-f]{40}", v or "") and \
            _git_bytes("cat-file", "-e", v).returncode == 0:
        return v
    # clone may be stale — fetch once and retry
    _git_bytes("fetch", "origin", "--tags", "--quiet")
    if v in _tags():
        return v
    if re.fullmatch(r"[0-9a-f]{40}", v or "") and \
            _git_bytes("cat-file", "-e", v).returncode == 0:
        return v
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="unknown version")


@app.get("/v0/code/versions")
def code_versions():
    return {"versions": sorted(_tags())}


@app.get("/v0/code/{version}/games")
def code_games(version: str):
    import json
    v = resolve_version(version)
    p = _git_bytes("ls-tree", "--name-only", f"{v}:games")
    if p.returncode != 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="no games at this version")
    games = []
    for slug in p.stdout.decode().split():
        m = _git_bytes("show", f"{v}:games/{slug}/manifest.json")
        manifest = json.loads(m.stdout.decode()) if m.returncode == 0 else {}
        games.append({"slug": slug, "manifest": manifest})
    return {"version": v, "games": games}


@app.get("/v0/code/{version}/{path:path}")
def code_file(version: str, path: str):
    from fastapi import HTTPException
    from fastapi.responses import Response
    v = resolve_version(version)
    parts = [seg for seg in path.split("/") if seg not in ("", ".")]
    if not parts or ".." in parts:
        raise HTTPException(status_code=400, detail="bad path")
    clean = "/".join(parts)
    blob = _git_bytes("show", f"{v}:{clean}")
    if blob.returncode != 0:
        raise HTTPException(status_code=404, detail="no such file")
    media = "text/plain" if clean.endswith((".py", ".md", ".json")) \
        else "application/octet-stream"
    return Response(content=blob.stdout, media_type=media)
