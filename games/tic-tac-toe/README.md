# Tic-tac-toe

The reference implementation. Two seats, alternating turns, no hidden state —
the simplest game that exercises the whole protocol: room log, fold, validate,
render.

## Moves

- `place`: `{"cell": 0-8}` — cells are numbered left-to-right, top-to-bottom:

```
 0 | 1 | 2
---+---+---
 3 | 4 | 5
---+---+---
 6 | 7 | 8
```

Seat 0 plays X, seat 1 plays O.

## Playing solo vs your agent (phase 0)

No relay needed. The agent keeps the move list in the conversation, folds it
with `fold(moves)`, renders with `render(state)`, and plays the opposing seat
itself (random or greedy — its choice, it's the house).
