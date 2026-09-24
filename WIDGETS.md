# WIDGETS.md — the interactive canvas rule

**Rule: games ALWAYS render with the interactive canvas.** Every game in this
repo must ship a playable board widget. Text boards (`render()` in
`logic.py`) are a fallback for clients that can't show widgets — they are
never the primary experience.

## What the board widget is

`games/<slug>/board.html` — a compact HTML fragment (Muse `html_file`
widget kind) that shows the live game state and lets the human play by
tapping. The agent is still the game client: it validates and posts moves.
The widget is the human's hands, not the brain.

## How it works

1. **Template.** `board.html` contains placeholders: `__ROOM__`, `__SEAT__`,
   `__MARK__` (the human-readable mark, e.g. `X`), `__RELAY__` (base URL,
   e.g. `https://relay.onthe1.app`). It is not used directly.
2. **Instantiation.** The agent copies the template, replaces the
   placeholders for the current room, and creates an `html_file` widget from
   the concrete file.
3. **Live rendering.** The widget polls `GET {relay}/v0/rooms/{room}/moves`
   (public, CORS-enabled) every few seconds, folds the log in its own JS,
   and re-renders. Rival moves appear on their own — no agent round-trip
   needed for display.
4. **Taps.** Tapping a legal cell calls
   `window.hatchWidget.setState({selected: <cell>})`. The widget highlights
   the choice and shows "Sending your move…".
5. **The agent completes the loop.** The agent watches the widget's state
   (the `widget.state` tool). When `selected` appears, it re-folds the relay
   log, checks the tap is legal *right now* (its turn, cell empty, game not
   over), validates against `logic.py`, and POSTs the move. The widget sees
   the new move on its next poll, clears the selection, and re-renders.
6. **Trust boundary.** The widget never holds secrets and never POSTs. All
   writes go through the agent, which owns the handle secret and the
   validation. A tap is a *suggestion*; the agent decides.

## Authoring rules (for new games)

- **Theme-aware.** Use the `--hatch-widget-*` CSS variables; the board must
  look right in light and dark mode. No hard-coded white/black surfaces.
- **State in the bridge.** Interactive state lives in
  `window.hatchWidget.getState/setState`, never in `localStorage` (which is
  iframe-local and invisible to the agent).
- **No secrets, no writes.** The widget only ever GETs public relay
  endpoints. It must not contain handle secrets or POST moves.
- **Fold locally, simply.** Re-implement the game's fold in the widget's JS
  (it's a view concern; keep it small and readable). The agent's
  `logic.py` fold remains the authority — if they ever disagree, the log
  wins.
- **Only legal taps.** Disable or ignore taps on cells that aren't playable
  *right now* (wrong turn, occupied, game over). The agent re-checks anyway,
  but the UI shouldn't invite illegal moves.
- **Small.** Widgets replay with chat history; keep the fragment well under
  the 1 MB limit. No inlined media.
- **One widget per room.** Instantiate fresh per room; never reuse a widget
  across rooms (stale `__ROOM__` is a real bug source).

## The tap loop, precisely

```
human taps cell        ->  widget setState({selected: i})
agent sees selected    ->  GET moves, fold, is_terminal?
                           - terminal: announce result, stop watching
                           - turn == my seat and cell empty:
                               validate(state, move) via logic.py
                               POST /v0/rooms/{code}/moves
                           - else: ignore (stale/foreign tap)
widget polls, sees new move -> clears selection, re-renders
```

Races resolve naturally: the agent checks legality against the *current*
log at the moment of the tap, not the moment the widget rendered.
