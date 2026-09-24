# Battleship

The hidden-state game. Your fleet never leaves your computer — the protocol's
answer to "how do we sync state that must stay secret" is: **we don't**.

## How trust works (commit-reveal)

1. **Commit.** Before play, each player picks their fleet and a random nonce,
   and publishes only `sha256(canonical_json(fleet) + nonce)` to the relay.
   The fleets are now locked — nobody can see them, nobody can change them.
2. **Play.** Seats alternate shots. Shots are public; the **fleet owner**
   declares `hit` / `miss` / `sunk`, because only they can know. (The agent
   checks the shot against the fleet on your own computer and declares
   honestly — and step 3 is why lying is pointless.)
3. **Reveal.** After someone wins, both players publish `{fleet, nonce}`.
   Anyone can verify the commitments match and re-check every hit/miss claim
   against the real fleets. A liar is caught, with proof, forever in the log.

## Moves

- `commit`: `{"commitment": "<hex>"}` — the sha256 from `make_commitment`.
- `shot`: `{"cell": "B4"}` — grid A1..J10.
- `result`: `{"result": "hit"|"miss"|"sunk", "ship": "destroyer"}` — declared
  by the fleet owner only; `ship` required when `sunk`.
- `reveal`: `{"ships": {...}, "nonce": "..."}`.

## Fleet format

```json
{
  "carrier": ["A1", "A2", "A3", "A4", "A5"],
  "battleship": ["C3", "D3", "E3", "F3"],
  "cruiser": ["H1", "H2", "H3"],
  "submarine": ["B7", "C7", "D7"],
  "destroyer": ["F9", "G9"]
}
```

Your agent helps you place ships (or places them for you), keeps the fleet +
nonce private on your computer, and handles the commit/reveal bookkeeping.
