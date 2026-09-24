# Muse Games Protocol v0

## Principles

1. **Agents are the clients.** Every player is a Muse user. Their agent fetches
   game code, holds state, renders an interactive board, and talks to the
   relay.
2. **Async-first.** Turns may be seconds or days apart. No persistent
   connections; polling is the baseline. GamePigeon-style: one move per turn,
   then it resolves.
3. **Relay-first networking.** Players never connect to each other. One shared
   relay — an HTTPS API at `https://relay.onthe1.app` — holds lobbies, rooms,
   the code itself, and append-only room logs. (It stores state in Redis
   internally; players never touch Redis.)
4. **Event-sourced rooms.** The log is the truth; state is folded from moves.
5. **Deterministic logic.** Game code is pure functions of `(state, move)`.
   Simulations resolve identically everywhere, which doubles as cheat
   verification.
6. **Hidden state never touches the relay.** Private info lives only on the
   owner's computer.
7. **Interactive canvas, always.** Games render as a tappable board widget
   (WIDGETS.md). Text rendering is a fallback, never the primary experience.
8. **v0 trusts players, verifies afterwards.** The relay is a dumb pipe;
   cheating is detectable (commit-reveal, re-foldable logs), not prevented.
   Acceptable for friendly play.

## Roles

- **Game package** — versioned public code (this repo, or served by the relay
  itself). Manifest + pure logic + interactive board.
- **Player agent** — fetches the package, manages rooms for its human,
  presents the board, posts validated moves, nudges on turn changes.
- **Relay** — the HTTPS API. Rooms, move logs, lobbies, commitments, and the
  game code. Identity-checked (handle secrets, seat ownership) but
  game-rule-dumb in v0.

## Getting the code

A player agent needs the game package before it can play. Two equivalent
sources, same bytes:

1. **GitHub** (source of truth): `https://github.com/cromestant/muse-casual-games`
   — clone or fetch, check out the room's pinned version.
2. **The relay itself**: `GET /v0/code/{version}/games` lists what's available;
   `GET /v0/code/{version}/{path}` returns raw file bytes (e.g.
   `/v0/code/v0.1.0/games/tic-tac-toe/logic.py`). No GitHub access needed.

`{version}` is a signed release tag (`v0.1.0`) or an exact commit SHA.
GitHub is where releases are published and signed; the relay serves a clone
of it. Either way:

- **Pin the version.** The room records the exact commit; agents run that and
  nothing else for that room.
- **Verify the signature.** Release tags are SSH-signed by `cromestant`
  (GitHub shows them as Verified). Check before first run.
- **First-run approval.** Before executing a game package the first time, the
  agent shows the human what it is and what it will do, and gets a yes.
- **Sandbox.** Game code runs in its own directory; network egress limited to
  the relay host. Game code never sees the rest of the user's computer.

## Game package

`games/<slug>/` contains:

- `manifest.json` — game metadata (below).
- `logic.py` — the pure logic module. MUST expose (no I/O, no clock, no
  unseeded RNG):
  - `initial_state(config) -> state`
  - `validate(state, move) -> None` (raises on illegal move)
  - `apply(state, move) -> new_state` (must call `validate` first)
  - `is_terminal(state) -> bool`
  - `winners(state) -> [seats]`
  - `next_seats(state) -> [seats]` (whose turn it is)
  - `render(state, perspective_seat) -> str` (text board — fallback only)
- `make_board.py` — renders the interactive board widget (WIDGETS.md):
  takes the room, seat, mark, and move log, prints a standalone board HTML
  with the position baked in. **Required.** A game without a board renderer
  is not a game here.

```json
{
  "game": "mini-golf",
  "version": "0.1.0",
  "min_players": 2,
  "max_players": 4,
  "turn_policy": "alternating",
  "hidden_state": false,
  "phases": ["play"],
  "logic": "logic.py",
  "board": "make_board.py",
  "move_types": ["shot"]
}
```

## Identity

Self-chosen handle, e.g. `charles-7f3a`. Registered once:

```
POST /v0/players/register
{"handle": "charles-7f3a", "secret": "<invented, kept private>"}
```

The secret is stored as a hash. Every mutating call carries
`{handle, secret}`; the relay returns 401 on a bad secret. v0 is
friendly-play auth — good enough until there's a reason for public-key
challenges.

## Rooms — the messaging format

Rooms are created over HTTPS and identified by a short human-readable code
shared out-of-band (text it to your friend, like GamePigeon).

**Create:**

```
POST /v0/rooms
{"handle": "...", "secret": "...", "game": "tic-tac-toe",
 "version_sha": "<exact commit the room runs>",
 "seats": ["charles-7f3a", "rival-9b1c"],   // ordered; index == seat number
 "config": {}}
-> {"code": "KX7Q-2M4P"}
```

**Read:**

```
GET /v0/rooms/KX7Q-2M4P
-> {"game": "tic-tac-toe", "version_sha": "...",
    "seats": ["charles-7f3a", "rival-9b1c"], "status": "open|active|finished",
    "config": {}, "created_ts": 1758746994}
```

**Lifecycle:** `open` (waiting for seats) → `active` (first move posted) →
`finished` (any client may mark it finished when `is_terminal` folds true,
running the reveal phase first if the game has one).

## Moves — the log is the truth

**Post** (only the seat's owner; the relay checks handle-vs-seat, not rules):

```
POST /v0/rooms/KX7Q-2M4P/moves
{"handle": "...", "secret": "...", "seat": 1,
 "type": "shot", "payload": {"angle_deg": 42.5, "power": 0.73}}
-> {"seq": 3}
```

Wrong secret → 401. Seat not owned by handle → 403. Unknown room → 404.

**Read** (public — this is what agents poll to render boards):

```
GET /v0/rooms/KX7Q-2M4P/moves[?since=N]
-> {"moves": [
      {"seat": 1, "handle": "rival-9b1c", "type": "shot",
       "payload": {"angle_deg": 42.5, "power": 0.73}, "ts": 1758746994},
      ...
    ], "since": 0}
```

The envelope the client folds is `{"seat", "type", "payload"}`; `handle`
and `ts` are transport metadata. Rules for clients:

- **Validate locally before sending** (`validate(state, move)`) — catches
  misclicks before anything leaves the computer.
- **Re-validate on read.** A move that fails validation is ignored by honest
  clients and the offender's handle is flagged in chat. (v0: social policing.)
- **The log is the truth.** If local state disagrees with the log, re-fold.
  New joiners catch up by reading the whole log.

## Turn policies

- `alternating` — seats in fixed order; `next_seats` from logic. (Tic-tac-toe,
  mini golf.)
- `commit` — setup phase where every seat submits a commitment before play
  begins. (Battleship fleet placement.)
- Reserved for later: `simultaneous`, `free`.

## Hidden state

**Rule: anything a player shouldn't see never leaves their computer.**

Patterns:

- **Owner-declared.** Battleship: only the fleet owner can know whether a shot
  hit, so the owner declares `hit`/`miss`/`sunk`. Honesty is enforced by
  commit-reveal, not by authority.
- **Commit-reveal.** During the `commit` phase each seat publishes a
  commitment: `POST /v0/rooms/{code}/commits {"commitment": sha256(...)}`.
  After the game, everyone publishes `{"secret", "nonce"}` as `reveal` moves
  and any client can verify every commitment and re-check every claim made
  during play. A liar is caught, publicly, with proof. Read commitments via
  `GET /v0/rooms/{code}/commits`.
- **The dealer problem.** Card hands need someone to shuffle and deal without
  seeing. v0 does not solve this — card games wait until there's a
  relay-dealt design or a validating relay. Documented here so nobody builds
  a card game on v0 and acts surprised.

## Determinism

- `apply` must be pure: no wall clock, no RNG unless seeded from the log.
  If a game needs randomness, the seed is `sha256(room_code | seq)` — public,
  reproducible, and fixed before the move that uses it.
- Mini golf physics are fully determined by `(course, ball, shot)`: fixed
  timestep, no randomness at all. Same inputs → same rest position on every
  computer. Re-folding a room replays every shot bit-for-bit.

## Lobby & matchmaking

- `POST /v0/lobby/{game}/join` / `/leave` (authed), `GET /v0/lobby/{game}`
  (public) → `{"game": ..., "waiting": [{"handle": ..., "since_ts": ...}]}`.
- Any agent watching the lobby that sees `>= min_players` waiting may create
  a room and tell each human the code in chat. (First watcher wins; v0 keeps
  this human-speed, which makes races rare and harmless.)
- Private games skip the lobby: creator makes the room with chosen seats and
  shares the code directly.

## Notifications

- Baseline: the agent runs a periodic check (every few minutes): "any of my
  human's rooms where it's their turn and I haven't told them yet?" → chat
  nudge. Async-friendly, no infra.
- The agent pushes a fresh board widget whenever the position changes, so
  the human *sees* rival moves live (widgets can't fetch — see WIDGETS.md).

## Security model

- **Pin the SHA.** The room records the exact commit; agents refuse to run any
  other code for that room. Updating a game mid-room is impossible by design.
- **Signed releases.** Tags are SSH-signed by the publisher; clients verify
  before first run (GitHub shows Verified, or `git verify-tag`).
- **First-run approval.** The agent shows the human what the code is and gets
  a yes before executing.
- **Sandbox.** Game code runs in its own directory; network egress limited to
  the relay host.
- **Scope.** v0 is friendly play: no money, no ranked ladder. Cheating is
  detectable and socially policed.

## Versioning

Manifest `version` is semver; rooms pin the commit SHA, not the version
number. Exact SHA match required — a client may not substitute a different
checkout.

## Status & roadmap

Working today: relay rooms + private codes + lobby over the public HTTPS
API; code distribution from the relay; signed releases; interactive board
widgets; tic-tac-toe fully playable.

Next: battleship commit-reveal wired end-to-end over the API; mini-golf
course select; the player skill/connector so any Muse can discover and play
without a manual brief. Later: card games (needs the dealer design), and a
validating relay that checks moves against the rules (cheating becomes
impossible, not just detectable).
