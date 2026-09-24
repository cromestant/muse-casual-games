# PLAYER.md — how to play (agent brief)

You are a **player agent** for muse-casual-games: small turn-based games
played through Muse, async and GamePigeon-style. There is no app and no
website; you are the game client. Your human plays by tapping an
interactive board and chatting with you.

## The pieces

- **Relay:** `https://relay.onthe1.app` — the shared server. Rooms, move
  logs, lobby, **and the game code itself**. You talk to it with plain
  HTTPS; you never talk to the other player's computer.
- **Game code:** public at `https://github.com/cromestant/muse-casual-games`
  (source of truth, signed releases) and served by the relay
  (`/v0/code/...`, same bytes, no GitHub access needed).
- **A room** is one game: a short code (e.g. `KX7Q-2M4P`), a move log, and
  2+ seats. The log is the truth — you fold it through the game's `logic.py`
  to get the current state.

## Setup (once per human)

1. Check the relay: `GET https://relay.onthe1.app/health` → `{"ok": true}`.
2. **Register a handle** for your human (their screen name, e.g.
   `cromestant-8f2a`): `POST /v0/players/register`
   `{"handle": ..., "secret": ...}`. Invent a strong secret and **keep it**
   — every mutating call needs it, and anyone with it can play as this
   handle. Never print it in chat.

## Getting the game code

For the room's pinned version (a tag like `v0.1.0` or a commit SHA):

```
GET /v0/code/{version}/games          -> [{slug, manifest}, ...]
GET /v0/code/{version}/games/{slug}/logic.py
GET /v0/code/{version}/games/{slug}/board.html
GET /v0/code/{version}/games/{slug}/manifest.json
```

Or clone `https://github.com/cromestant/muse-casual-games` and check out
the version. Same bytes either way.

**Trust check (do not skip).** Release tags are SSH-signed by `cromestant`.
Before running a version the first time, verify the signature (GitHub shows
the tag as Verified, or `git verify-tag`). Refuse to run any other code for
the room. If your human hasn't approved running this game code before, show
them what it is and get a yes first.

## Starting or joining a game

**Private game (a code, like GamePigeon):**
- Creator: `POST /v0/rooms` with
  `{handle, secret, game, version_sha, seats: [creator, friend], config: {}}`.
  You get back a `code`. Your human sends that code to their friend
  out-of-band (text message). `version_sha` is the exact commit the room
  runs — every client must run that and nothing else.
- Joiner: `GET /v0/rooms/{code}` to read the room, fetch that version's
  code, run the trust check above, and you're in. No explicit "join" call —
  posting a move as your seat is joining.

**Matchmaking:** `POST /v0/lobby/{game}/join`, then poll
`GET /v0/lobby/{game}`. When enough players are waiting, any watcher may
create the room and tell each human the code.

## Presenting the game — the interactive board, always

**Games ALWAYS render with the interactive canvas.** When a game starts (and
whenever it's your human's turn), instantiate the game's `board.html`:

1. Copy the template, replacing `__ROOM__`, `__SEAT__` (your human's seat),
   `__MARK__` (their mark, e.g. `X`), `__RELAY__` (the relay base URL).
2. Create an `html_file` widget from the concrete file and show it in chat.

The board polls the relay itself and re-renders live — your human sees rival
moves without you doing anything. Taps land in the widget's state as
`selected: <cell>`; they are *suggestions*, not moves. See WIDGETS.md for
the full pattern.

The turn loop:

1. **Watch** the widget state and the relay. Poll
   `GET /v0/rooms/{code}/moves` every few minutes for each of your human's
   non-finished rooms too (no push in v0).
2. When a tap appears: fold the log with the game's `logic.py`, and check
   the tap is legal *right now* — game not terminal, it's your human's
   turn, cell empty.
3. **Validate locally first** (`validate(state, move)`) — this catches
   misclicks before anything is sent.
4. `POST /v0/rooms/{code}/moves`
   `{handle, secret, seat, type, payload}`. The relay checks the handle
   owns the seat (wrong seat → 403); it does not check game rules.
   **You are responsible for only ever sending legal moves.**
5. The board sees the new move on its next poll and re-renders by itself.
6. If `is_terminal(state)`: announce the result (`winners(state)`) and
   `POST /v0/rooms/{code}/finish`.

## Rules you must follow

- **Hidden state never touches the relay.** If a game has private info
  (battleship fleets), it stays on your computer. See PROTOCOL.md.
- **The widget never holds secrets and never POSTs.** All writes go through
  you. A tap is a suggestion; you decide.
- **One move per turn, yours only.** Never post for another seat.
- **The log is the truth.** If your local state disagrees with the log,
  the log wins — re-fold.
- **Async is normal.** Turns may be seconds or days apart. Never rush the
  human; just nudge when it's their turn.

## Games available

Ask the relay — `GET /v0/code/v0.1.0/games` is the live list. (Today:
tic-tac-toe is fully playable with a board; battleship and mini-golf have
logic in the repo and are getting their boards next.)

## If something looks wrong

- 401 → bad handle/secret. Re-register or fix the secret.
- 403 on a move → the seat doesn't belong to your handle. Check `seats`
  in the room meta.
- 404 on a room → wrong code (codes are case-sensitive), or on
  `/v0/code/...` → unknown version or path.
- Relay down or unreachable → tell your human plainly; the game waits.
  Nothing is lost: the log persists on the relay.
