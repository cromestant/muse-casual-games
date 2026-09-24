# WIDGETS.md — the interactive canvas rule

**Rule: games ALWAYS render with the interactive canvas.** Every game in this
repo must ship a playable board widget. Text boards (`render()` in
`logic.py`) are a fallback for clients that can't show widgets — they are
never the primary experience.

## What the board widget is

A compact HTML fragment (Muse `html_file` widget kind) that shows the
current game position and lets the human play by tapping. The agent is still
the game client: it polls the relay, validates, and posts moves. The widget
is the human's hands and eyes, not the brain.

## Key constraint: widgets have no network access

Chat clients sandbox widget iframes: `fetch()` to the relay (or anywhere)
fails inside the widget. Verified 2026-09-24 — both players' boards sat on
"Reconnecting…" forever while taps worked fine. **The widget therefore never
fetches.** All relay I/O happens in the agent; the position is baked into
the HTML at creation time.

## How it works

1. **Renderer.** `games/<slug>/make_board.py` takes the room, seat, mark,
   and the move log (a bare JSON list of moves, or the raw
   `GET /v0/rooms/{code}/moves` response) and prints a complete standalone
   board HTML: the current position rendered as buttons, the status line
   ("Your move — tap a cell" / "Rival's turn…" / result), and a tiny script
   that only handles taps. No polling, no fetch.
2. **Push.** Whenever the position changes — the agent's poll sees a new
   move in the log, or the agent posts the human's move — the agent runs
   `make_board.py`, creates a fresh `html_file` widget, and embeds it in
   chat. The human always sees the latest position without doing anything.
3. **Taps.** Tapping a legal cell calls
   `window.hatchWidget.setState({selected: <cell>})`. The widget highlights
   the choice and shows "Sending your move…". (State lives in the widget
   bridge, which works fine — only network is blocked.)
4. **The agent completes the loop.** The agent watches the *current*
   widget's state (the `widget.state` tool). When `selected` appears, it
   re-folds the relay log, checks the tap is legal *right now* (its turn,
   cell empty, game not over), validates against `logic.py`, and POSTs the
   move. Then it pushes a fresh board showing the new position.
5. **Trust boundary.** The widget never holds secrets and never talks to
   the relay at all. All reads and writes go through the agent, which owns
   the handle secret and the validation. A tap is a *suggestion*; the agent
   decides.
6. **One live board.** Only the newest board widget for a room accepts taps
   — the agent watches that widget's id. Taps on older (stale) boards in the
   chat history are ignored. Name each board's `display_text` with the room
   and the position summary so history stays readable.

## Authoring rules (for new games)

- **Theme-aware.** Use the `--hatch-widget-*` CSS variables; the board must
  look right in light and dark mode. No hard-coded white/black surfaces.
- **State in the bridge, position baked in.** Interactive state lives in
  `window.hatchWidget.getState/setState`, never in `localStorage` (which is
  iframe-local and invisible to the agent). The *position* is plain HTML/JS
  baked in at render time — never fetched.
- **No secrets, no network.** The widget makes zero network requests. It
  must not contain handle secrets.
- **Only legal taps.** Disable or ignore taps on cells that aren't playable
  *right now* (wrong turn, occupied, game over). The agent re-checks anyway,
  but the UI shouldn't invite illegal moves.
- **Small.** Widgets replay with chat history; keep the fragment well under
  the 1 MB limit. No inlined media.
- **One widget per position.** A new position means a new widget. Never try
  to update a widget in place — there is no update primitive; push fresh.

## The tap loop, precisely

```
agent polls relay, sees new move -> make_board.py -> new widget in chat
human taps cell                  ->  widget setState({selected: i})
agent sees selected              ->  GET moves, fold, is_terminal?
                                     - terminal: push final board, announce, stop
                                     - turn == my seat and cell empty:
                                         validate(state, move) via logic.py
                                         POST /v0/rooms/{code}/moves
                                         push fresh board
                                     - else: ignore (stale/foreign tap)
```

Races resolve naturally: the agent checks legality against the *current*
log at the moment of the tap, not the moment the board was rendered.
Idempotency: never POST the same tap twice — after posting, re-fold before
any further post; if the tapped cell already holds your mark, the tap is
already served.

## Why not let the widget poll? (history)

The original design had the widget poll `GET /v0/rooms/{room}/moves`
itself (CORS is enabled on the relay). It never worked: the chat client's
widget sandbox blocks external network on all tested clients, so both
players' boards were stuck on "Reconnecting…". The relay keeps its CORS
headers (harmless, and useful if a future client allows widget network),
but no game may depend on widget-initiated network.
