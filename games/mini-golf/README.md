# Mini golf

GamePigeon-style async mini golf: one shot per turn, then it resolves. You
chat your shot ("45 degrees, 70% power"), your agent runs it through the
physics sim, and the result syncs to everyone.

## Moves

- `shot`: `{"angle_deg": 0-360, "power": 0.0-1.0}` — 0° is +x (east),
  90° is +y. Full power = 40 units/sec.

## Why it's deterministic (and why that matters)

The sim uses a fixed timestep (1/240s), has no randomness and no clock.
Identical `(course, ball, shot)` → identical rest position on every computer.
That means:

- Nobody needs to trust the shooter's agent about where the ball ended up —
  every client simulates every shot locally when folding the log.
- Disputes are settled by re-running, not by arguing.

## Rules

- Seats alternate shots per hole until everyone holes out (or hits the
  8-stroke cap — stragglers pick up and score 9).
- Lowest total strokes across all holes wins.
- Ball must be slow enough when reaching the cup or it lips out (keep an eye
  on that last wall bounce).

## Courses

`courses.json` holds named courses; rooms pick one in `config`. `rookie-3`
ships with the game: Straightaway, The Elbow, Pillar. Adding a course is just
walls + tee + cup — send a PR.
