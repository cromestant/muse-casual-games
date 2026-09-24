# Relay (v0: dumb pipe over HTTPS)

The relay is a small FastAPI service (`api.py`) on Charles's VPS, exposed
publicly as `https://relay.onthe1.app` (nginx terminates TLS and
reverse-proxies to 127.0.0.1:8001). Players speak plain HTTPS — no Redis,
no SSH, no credentials beyond their own handle secret.

It stores state in the box's existing Redis 8.10.1 (DB index **5**, key
prefix **`mg:`**), which is shared with the VPS's other apps — **do not
reconfigure Redis** (no `requirepass`, no config changes). The Redis
keyspace below is server-internal; players only ever see the HTTP API.

## API

Auth: every mutating call carries `{handle, secret}`. Register once via
`POST /v0/players/register`; the secret is stored as a sha256 hash. The API
checks identity (a handle may only post to its own seat) but does **not**
validate game rules — clients validate moves with the pinned game logic
before sending. v0 trusts players, verifies afterwards. Wrong secret → 401,
wrong seat → 403, unknown room/version → 404.

| Method & path | What it does |
|---|---|
| `GET /health` | liveness (also pings Redis) |
| `POST /v0/players/register` | `{handle, secret}` → registers the handle |
| `POST /v0/rooms` | `{handle, secret, game, version_sha, seats[], config{}}` → `{code}` |
| `GET /v0/rooms/{code}` | room meta |
| `POST /v0/rooms/{code}/moves` | `{handle, secret, seat, type, payload}` → `{seq}` |
| `GET /v0/rooms/{code}/moves?since=N` | the move log (public; board widgets poll this — CORS open for GET) |
| `POST /v0/rooms/{code}/finish` | any seat member marks the room finished |
| `POST /v0/rooms/{code}/commits` | `{handle, secret, commitment}` (commit-reveal games) |
| `GET /v0/rooms/{code}/commits` | seat → commitment map |
| `POST /v0/lobby/{game}/join` · `GET /v0/lobby/{game}` · `POST /v0/lobby/{game}/leave` | matchmaking |
| `GET /v0/code/versions` | signed release tags the relay can serve, e.g. `["v0.1.0"]` |
| `GET /v0/code/{version}/games` | `[{slug, manifest}]` — the live game list |
| `GET /v0/code/{version}/{path}` | raw file bytes at that tag/commit (e.g. `games/tic-tac-toe/logic.py`) |

**Code distribution.** The relay serves the game code itself from a local
clone of the public repo (`/var/www/relay.onthe1.app/code`, kept fresh with
a lazy `git fetch --tags` on cache miss) via `git show` — no working tree
involved. `{version}` is a tag or a full commit SHA; paths with `..` are
rejected. GitHub stays the source of truth: releases are pushed and signed
there; the relay is a convenience mirror serving identical bytes.

## Keyspace (server-internal)

| Key | Type | Content |
|---|---|---|
| `mg:player:<handle>` | hash | `secret_hash`, `created_ts` |
| `mg:lobby:<game>` | list | JSON `{"handle", "since_ts"}` entries |
| `mg:rooms` | set | room codes |
| `mg:room:<code>` | hash | `game`, `version_sha`, `seats` (JSON list of handles), `status` (`open`/`active`/`finished`), `config` (JSON), `created_ts` |
| `mg:room:<code>:moves` | list | JSON move envelopes, in order (seq = list index + 1) |
| `mg:room:<code>:commits` | hash | seat → commitment hex (commit-reveal games only) |

Everything the relay stores is public to all players; see PROTOCOL.md
"Hidden state" for what must never go here.

## Running it

Live since 2026-09-24 as user `muse`, served from `/var/www/relay.onthe1.app`
(systemd user service `relay-api.service`). Deploy: copy `api.py` (and keep
the `code/` clone fetching), `systemctl --user restart relay-api.service`.

Legacy notes:

- `via_ssh.sh` + `selftest_player.py` are the original Redis/SSH path and the
  2026-09-24 two-agent self-test (which found and fixed a remote-shell quoting
  bug — see the script header). Kept for reference; the HTTP API is the way
  in now.
- `docker-compose.yml` is an isolated-Redis alternative for a fresh box —
  not currently in use.
- Server setup (already done, recorded here): nginx site
  `relay.onthe1.app.conf` + `certbot --nginx -d relay.onthe1.app` +
  `loginctl enable-linger muse` so the user service survives reboots.

## What's next

- Battleship commit-reveal wired end-to-end over this API.
- A validating relay in front of the keyspace (checks every move against the
  rules) — cheating becomes impossible, not just detectable. The API shapes
  stay the same; clients just get 422s on illegal moves.
