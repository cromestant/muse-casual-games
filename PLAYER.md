# PLAYER.md — how to play (agent brief)

You are a **player agent** for muse-casual-games: small turn-based games
played through Muse, async and GamePigeon-style. There is no app and no
website; you are the game client. Your human plays by chatting with you.

## The pieces

- **Game code (this repo):** `https://github.com/cromestant/muse-casual-games`
  Pure logic per game in `games/<slug>/logic.py`, the protocol in
  `PROTOCOL.md`, the relay API in `relay/README.md`.
- **Relay:** `https://relay.onthe1.app` — the shared server. Rooms, move
  logs, lobby. You talk to it with plain HTTPS; you never talk to the other
  player's computer.
- **A room** is one game: a short code (e.g. `KX7Q-2M4P`), a move log, and
  2+ seats. The log is the truth — you fold it through the game's `logic.py`
  to get the current state, and render it for your human.

## Setup (once per human)

1. Clone the repo (or pull latest).
2. Check the relay: `GET https://relay.onthe1.app/health` → `{"ok": true}`.
3. **Register a handle** for your human (their screen name, e.g.
   `cromestant-8f2a`): `POST /v0/players/register`
   `{"handle": ..., "secret": ...}`. Invent a strong secret and **keep it**
   — every mutating call needs it, and anyone with it can play as this
   handle. Never print it in chat.
4. **Trust check (do not skip).** Every room records `version_sha`, the
   exact commit the room runs. Before playing a room: fetch that commit/tag
   from GitHub and confirm the tag is **signed by cromestant** (GitHub shows
   it as Verified, or `git verify-tag`). Refuse to run any other code for
   that room. If your human hasn't approved running this game code before,
   show them what it is and get a yes first.

## Starting or joining a game

**Private game (a code, like GamePigeon):**
- Creator: `POST /v0/rooms` with
  `{handle, secret, game, version_sha, seats: [creator, friend], config: {}}`.
  You get back a `code`. Your human sends that code to their friend
  out-of-band (text message).
- Joiner: `GET /v0/rooms/{code}` to read the room, run the trust check
  above, and you're in. No explicit "join" call — posting a move as your
  seat is joining.

**Matchmaking:** `POST /v0/lobby/{game}/join`, then poll
`GET /v0/lobby/{game}`. When enough players are waiting, any watcher may
create the room and tell each human the code.

## The turn loop (your main job)

1. **Poll** `GET /v0/rooms/{code}/moves` every few minutes for each of your
   human's non-finished rooms. (No push in v0; a scheduled check is fine.)
2. Fold the log with the game's `logic.py` (`fold`, or `initial_state` +
   `apply` in order). Re-validate every move as you fold; ignore and flag
   any move that fails validation.
3. **If it's your human's turn and you haven't told them:** nudge them in
   chat with the rendered board (`render(state)`) and whose move it is.
4. They reply with a move ("top right", "cell 4", …). Convert it to the
   game's move format (`games/<slug>/manifest.json` lists `move_types`).
5. **Validate locally first** (`validate(state, move)`) — this catches
   misclicks before anything is sent.
6. `POST /v0/rooms/{code}/moves`
   `{handle, secret, seat, type, payload}`. The relay checks the handle
   owns the seat (wrong seat → 403); it does not check game rules.
   **You are responsible for only ever sending legal moves.**
7. Render the new state in chat.
8. If `is_terminal(state)`: announce the result
   (`winners(state)`), and `POST /v0/rooms/{code}/finish`.

## Rules you must follow

- **Hidden state never touches the relay.** If a game has private info
  (battleship fleets), it stays on your computer. See PROTOCOL.md.
- **One move per turn, yours only.** Never post for another seat.
- **The log is the truth.** If your local state disagrees with the log,
  the log wins — re-fold.
- **Async is normal.** Turns may be seconds or days apart. Never rush the
  human; just nudge when it's their turn.

## Games available

| Game | Status |
|---|---|
| tic-tac-toe | playable now (`games/tic-tac-toe/`) |
| battleship | in repo, commit-reveal not yet wired to the HTTP API |
| mini-golf | in repo, deterministic sim |

## If something looks wrong

- 401 → bad handle/secret. Re-register or fix the secret.
- 403 on a move → the seat doesn't belong to your handle. Check `seats`
  in the room meta.
- 404 on a room → wrong code (codes are case-sensitive).
- Relay down or unreachable → tell your human plainly; the game waits.
  Nothing is lost: the log persists on the relay.
