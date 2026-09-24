# muse-games

Small async games played through Muse. Every player is a Muse user: their agent
fetches the game code, runs it on their own computer, renders the game in chat,
and syncs through one shared relay.

No game servers. No accounts. Just a protocol, public game code, and a Redis.

## The idea in one paragraph

Game code lives in public (this repo). When you want to play, your Muse agent
fetches the game, shows you what it will run, and hosts it for you — you play
by chatting ("I shoot at B4", "putter, 70% power, slight left"). Game state
syncs between players through a dumb central relay (Redis on a VPS): each room
is an append-only log of moves, and every client folds the log into the current
state. Turns can be seconds or days apart; your agent nudges you when it's your
move. Think GamePigeon, but the client is a conversation.

## Repo layout

```
muse-games/
  README.md            # this file
  PROTOCOL.md          # the v0 protocol: rooms, moves, identity, trust, security
  relay/               # the dumb relay: Redis keyspace, docker-compose, ops notes
  games/
    tic-tac-toe/       # reference implementation (complete)
    battleship/        # hidden state via commit-reveal (complete logic)
    mini-golf/         # deterministic physics sim (working sim + 1 course)
  agents/
    AGENT.md           # playbook: how a Muse agent hosts/plays a game
```

## Phase plan

- **Phase 0** — solo play vs your agent. No relay. Proves the "played through
  Muse" UX. (Tic-tac-toe is playable this way today.)
- **Phase 1** — relay rooms + private game codes. Tic-tac-toe, then battleship
  (forces the hidden-state design: commit-reveal).
- **Phase 2** — lobby + random matchmaking. Mini golf, then card games (forces
  the dealer/trust design).
- **Phase 3** — validating relay: a small service in front of Redis that checks
  every move against the rules before accepting it. Kills cheating for real.

## Design decisions (the short version)

See [PROTOCOL.md](PROTOCOL.md) for the full story.

- **Event-sourced rooms.** The move log is the truth; state is folded from it.
  Replays, audits, and catch-up for new joiners are free.
- **Deterministic logic.** Game code is pure functions of `(state, move)`. Mini
  golf physics resolve identically on every computer — anyone can re-verify a
  shot, which is also the anti-cheat story.
- **Hidden state never touches the relay.** Battleship fleets and card hands
  live only on the owner's computer. Battleship honesty comes from
  commit-reveal: placements are hashed before play, revealed after, and every
  hit/miss claim is checkable.
- **Relay-first networking.** Players never connect to each other (NAT,
  strangers, no shared network). The Redis relay holds lobbies, rooms, and logs.
- **v0 trusts players, verifies afterwards.** Fine for friendly play. The
  validating relay (phase 3) makes cheating impossible for turn-based games.

## Try it

Clone this repo, then have your Muse agent read `agents/AGENT.md`. It knows
what to do from there. To play tic-tac-toe against your agent right now, just
ask it.
