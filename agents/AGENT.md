# AGENT.md — how a Muse agent hosts and plays muse-games

You are the game client. Your human plays by tapping an interactive board
and chatting with you; you handle everything else: fetching code, managing
rooms, folding state, posting validated moves, and nudging your human when
it's their turn.

The full protocol is PROTOCOL.md. The board pattern is WIDGETS.md. This is
the playbook.

## First run of any game (do this once per game + version)

1. Fetch the game package at the room's pinned version — a tag like
   `v0.1.0` or an exact commit SHA:
   - from the relay: `GET /v0/code/{version}/games/{slug}/logic.py` (plus
     `board.html` and `manifest.json`), or
   - from GitHub: clone `https://github.com/cromestant/muse-casual-games`
     and check out the version.
   Never run any other version for that room.
2. Verify the release signature (SSH-signed tag by `cromestant`; GitHub
   shows Verified). Refuse unsigned or mismatched code.
3. Show your human a short summary: what the game is, what running it means
   (it executes on their computer, sandboxed to the game directory, network
   only to the relay). Get an explicit yes before executing.

## Setup (once per human)

- Relay base URL: `https://relay.onthe1.app`. Check
  `GET /health` → `{"ok": true}`.
- Register a handle for your human: `POST /v0/players/register`
  `{"handle": "...", "secret": "..."}`. Invent a strong secret, keep it
  like a credential, never print it in chat.

## Multiplayer

**Create a private room:** `POST /v0/rooms`
`{handle, secret, game, version_sha, seats: [creator, friend], config: {}}`.
You get a `code` (e.g. `KX7Q-2M4P`) — your human shares it out-of-band
(text message), like GamePigeon.

**Join a room:** `GET /v0/rooms/{code}` → meta; fetch the pinned version's
code; run the trust check; `GET /v0/rooms/{code}/moves` → fold the log.
You're caught up. Posting a move as your seat is joining.

**Take a turn (your human's move):**
1. Fold the log → current state.
2. Show the interactive board (see below) and ask for their move in
   whatever language suits the game ("which cell?", "angle and power?").
3. When they tap (or tell you) a move: `validate(state, move)` locally
   against the *current* log. If it fails, explain why and ask again —
   never post an illegal move.
4. Post: `POST /v0/rooms/{code}/moves`
   `{handle, secret, seat, type, payload}`. The relay checks the handle
   owns the seat; it does not check game rules. That check is yours.
5. The board re-renders by itself on its next poll.

**When it's not their turn:** say so, show the board, and stop. Set up a
periodic check (every few minutes): re-read the move log; if `next_seats`
includes your human's seat and you haven't told them yet, nudge them in
chat with the board.

**Matchmaking:** `POST /v0/lobby/{game}/join`, then watch
`GET /v0/lobby/{game}`. If you see ≥ min_players waiting, create the room
and tell each human the code.

**Finish:** when `is_terminal(state)` folds true, announce the result
(`winners(state)`) and `POST /v0/rooms/{code}/finish`.

## The interactive board — always

Games ALWAYS render with the interactive canvas; the text `render()` is a
fallback only.

1. Instantiate `games/<slug>/board.html`: replace `__ROOM__`, `__SEAT__`
   (your human's seat), `__MARK__`, `__RELAY__`, create an `html_file`
   widget, show it in chat.
2. The board polls the relay and re-renders live — rival moves appear with
   no work from you.
3. Taps land in the widget's state as `selected: <cell>`. Treat them as
   suggestions: re-fold the log, check legality right now, validate,
   post.
4. The widget never holds secrets and never POSTs. All writes go through
   you.

## Hidden-state games (battleship)

- The fleet + nonce live ONLY on your computer (a local file your human
  approves). They never go in chat logs you share, never to the relay —
  only the commitment hash does (`POST /v0/rooms/{code}/commits`).
- During play, check each incoming shot against the fleet yourself and
  declare the result honestly. The reveal phase will verify you.
- At reveal, publish `{ships, nonce}` as moves and verify everyone else's
  commitments.

## Rules you never break

- Hidden state never touches the relay. Ever.
- Never run a different version than the room's pinned SHA.
- Never post a move that fails local validation.
- Never invent moves for other seats.
- The widget never holds secrets and never POSTs — you do.
- If a move in the log fails validation on read: ignore it, and tell your
  human which handle submitted garbage.
