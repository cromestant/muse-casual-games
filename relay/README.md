# Relay (v0: dumb pipe)

One Redis. No custom server code in v0 — the relay is purely a shared
append-only log plus a lobby. Agents speak Redis directly (or through a thin
wrapper). Everything the relay stores is public to all players; see
PROTOCOL.md "Hidden state" for what must never go here.

## Keyspace

| Key | Type | Content |
|---|---|---|
| `mg:player:<handle>` | hash | `secret_hash`, `created_ts` |
| `mg:lobby:<game>` | list | JSON `{"handle", "since_ts"}` entries |
| `mg:rooms` | set | room codes |
| `mg:room:<code>` | hash | `game`, `version_sha`, `seats` (JSON list of handles), `status` (`open`/`active`/`finished`), `config` (JSON), `created_ts` |
| `mg:room:<code>:moves` | stream | move envelopes (see PROTOCOL.md) |
| `mg:room:<code>:commits` | hash | seat → commitment hex (commit-reveal games only) |

## Flows

**Private room (game code):**
1. Creator's agent: `HSET mg:room:GOLF-7Q2P game mini-golf version_sha <sha> seats '["a","b"]' status open ...`, `SADD mg:rooms GOLF-7Q2P`.
2. Creator texts the code to their friend.
3. Friend's agent reads the room hash, verifies the SHA, fetches that exact
   game commit, folds any existing moves.
4. Play: turn-holder's agent validates locally, then `XADD mg:room:<code>:moves * ...`.

**Matchmaking:**
1. Agent: `RPUSH mg:lobby:tic-tac-toe '{"handle":"x","since_ts":...}'`.
2. Any watching agent sees length ≥ min_players, `LPOP`s that many handles,
   creates the room, and tells each human the code in chat.

## Running it (live)

The relay is live on `server.onthe1.app` (Charles's Ubuntu VPS) since
2026-09-24. It uses the **already-running Redis 8.10.1** on 127.0.0.1:6379 —
shared with the box's existing apps (nginx/PHP/FastAPI), so **do not
reconfigure it** (no `requirepass`, no config changes; it has no password and
must stay that way for the existing apps).

- **Game keyspace:** DB index **5**, key prefix **`mg:`** (e.g.
  `mg:room:{id}:moves`). DB 5 is otherwise empty; DB 0 holds the existing
  apps' keys — leave it alone.
- **Access:** localhost-only in phase 1. Agents reach it via SSH:
  `ssh vps` (user `muse`, key in place) then `redis-cli -n 5 …`, or a tunnel:
  `ssh -L 6379:localhost:6379 -N vps`. Nothing is exposed publicly.
- **Phase 2 (stranger matchmaking):** expose Redis with TLS +
  `requirepass` on `relay.onthe1.app`, or run the isolated instance below.

`docker-compose.yml` in this directory is the isolated-instance alternative
(dedicated Redis with password, for phase 2 or a fresh box) — not currently
in use.

```yaml
services:
  redis:
    image: redis:7-alpine
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}", "--appendonly", "yes"]
    ports:
      - "100.100.x.x:6379:6379"   # VPS tailnet IP only
    volumes:
      - ./data:/data
    restart: unless-stopped
```

Notes:

- v0 assumes a trusted network path to the relay (Tailscale, or TLS +
  `--requirepass`). Redis 7 supports TLS natively if you need public-internet
  exposure — do that before inviting strangers.
- Back up `./data` (AOF is on). Losing the relay loses live rooms; finished
  games can be re-folded from any client's copy of the log, so ask players to
  keep logs of games they care about.
- Phase 3 replaces direct Redis access with a small validating HTTP service in
  front of it. The keyspace stays the same; agents just stop speaking Redis
  directly.
