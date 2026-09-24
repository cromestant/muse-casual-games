# muse-games (public repo: `muse-casual-games`)

Small async games played through Muse. Every player is a Muse user: their
agent fetches the game code, runs it on their own computer, shows an
interactive board in chat, and syncs through one shared relay.

No game servers. No accounts. Just a protocol, public game code, and a
relay with an HTTPS API.

## The idea in one paragraph

Game code lives in public (this repo, and served by the relay itself). When
you want to play, your Muse agent fetches the game at the exact version the
room pins, shows you what it will run, and hosts it for you — you play by
tapping the board ("put the X top-right", "I shoot at B4"). Game state syncs
between players through a dumb central relay (`https://relay.onthe1.app`):
each room is an append-only log of moves, and every client folds the log
into the current state. Turns can be seconds or days apart; your agent nudges
you when it's your move. Think GamePigeon, but the client is a conversation.

## Repo layout

```
muse-casual-games/
  README.md            # this file
  PROTOCOL.md          # the protocol: getting code, rooms, moves, identity, trust
  WIDGETS.md           # the interactive-canvas rule: every game ships a board
  PLAYER.md            # agent brief: how to fetch, join, and play a game
  relay/               # the relay API (FastAPI) + ops notes
  games/
    tic-tac-toe/       # reference implementation: logic + board, fully playable
    battleship/        # hidden state via commit-reveal (logic done, board next)
    mini-golf/         # deterministic physics sim (logic done, board next)
  agents/
    AGENT.md           # playbook: how a Muse agent hosts/plays a game
```

## How it fits together

- **Relay** (`relay/`, live at `https://relay.onthe1.app`): rooms, move
  logs, lobbies, commitments — and the game code itself
  (`GET /v0/code/{version}/...`). Identity-checked, game-rule-dumb.
- **Protocol** (`PROTOCOL.md`): how agents get the code, the exact message
  formats for rooms and moves, hidden-state patterns, the security model.
- **Boards** (`WIDGETS.md`): every game renders as a tappable board widget,
  always. The widget polls the relay and re-renders live; taps flow back to
  the agent, which validates and posts the move.
- **Trust**: rooms pin the exact commit; releases are SSH-signed tags;
  agents verify before first run.

## Status

Working: relay rooms + private codes + lobby over the public HTTPS API,
code distribution from the relay, signed releases (`v0.1.0`), interactive
board widgets, tic-tac-toe fully playable end-to-end.

Next: battleship commit-reveal wired end-to-end, mini-golf course select,
boards for both, and the player skill/connector so any Muse can discover and
play without a manual brief.

## Try it

Have your Muse agent read `PLAYER.md`. It knows what to do from there — or
ask it to start a tic-tac-toe game and tap away.
