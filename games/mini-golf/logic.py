"""Mini golf — GamePigeon-style async turn-based golf.

One move = one shot: {"angle_deg", "power"}. The shot resolves through a
DETERMINISTIC physics sim: fixed timestep, no randomness, no wall clock.
Same (course, ball, shot) -> same rest position on every computer, so any
client (or auditor) can re-verify any shot by re-folding the log.

Turns alternate between seats on each hole until everyone holes out (or hits
the stroke cap); then the next hole. Lowest total strokes wins.

Course format (courses.json): each hole has walls (line segments), a tee
(start position) and a cup (position + capture radius). Units are arbitrary.
"""

import json
import math

DT = 1 / 240          # fixed timestep: determinism's best friend
MAX_T = 30            # give up after 30 simulated seconds (should never hit)
FRICTION = 0.55       # velocity retained per second: v *= (1 - FRICTION*DT)
RESTITUTION = 0.75    # wall bounce energy retention
MAX_SPEED = 40        # speed at power = 1.0
CAPTURE_SPEED = 6     # ball must be slower than this to drop in the cup
STROKE_CAP = 8        # pick the ball up after 8; scored as 9


def initial_state(config=None):
    config = config or {}
    course = config.get("course", "rookie-3")
    seats = config.get("seats", [0, 1])
    holes = _load_course(course)
    return {
        "course": course,
        "hole_index": 0,
        "holes": len(holes),
        "balls": {s: _tee(holes[0]) for s in seats},   # seat -> [x, y]
        "strokes": {s: [0] * len(holes) for s in seats},
        "holed": {s: [False] * len(holes) for s in seats},
        "turn": seats[0],
        "seats": seats,
        "winner": None,
    }


def validate(state, move):
    if move["type"] != "shot":
        raise ValueError(f"unknown move type: {move['type']}")
    if move["seat"] != state["turn"]:
        raise ValueError("not your turn")
    if state["winner"] is not None:
        raise ValueError("game is over")
    p = move["payload"]
    if not (0 <= p["power"] <= 1):
        raise ValueError("power must be 0..1")
    # angle is free-form degrees; normalized in apply


def apply(state, move):
    validate(state, move)
    s = json.loads(json.dumps(state))
    # JSON turns int keys into strings; normalize back.
    s["balls"] = {int(k): v for k, v in s["balls"].items()}
    s["strokes"] = {int(k): v for k, v in s["strokes"].items()}
    s["holed"] = {int(k): v for k, v in s["holed"].items()}

    seat = move["seat"]
    hole = _load_course(s["course"])[s["hole_index"]]
    ang = math.radians(move["payload"]["angle_deg"] % 360)
    power = move["payload"]["power"]
    pos = list(s["balls"][seat])
    vel = [math.cos(ang) * power * MAX_SPEED,
           math.sin(ang) * power * MAX_SPEED]

    holed = _simulate(hole, pos, vel)

    s["balls"][seat] = pos
    h = s["hole_index"]
    s["strokes"][seat][h] += 1
    if holed:
        s["holed"][seat][h] = True

    if all(s["holed"][p][h] or s["strokes"][p][h] >= STROKE_CAP
           for p in s["seats"]):
        # Everyone finished the hole (stragglers pick up at cap+1).
        for p in s["seats"]:
            if not s["holed"][p][h]:
                s["strokes"][p][h] = STROKE_CAP + 1
        if h + 1 >= s["holes"]:
            s["winner"] = _leader(s)
        else:
            s["hole_index"] = h + 1
            new_hole = _load_course(s["course"])[h + 1]
            s["balls"] = {p: _tee(new_hole) for p in s["seats"]}
            s["turn"] = s["seats"][0]
    else:
        # Next seat that still has a ball on this hole.
        order = s["seats"]
        i = order.index(s["turn"])
        for k in range(1, len(order) + 1):
            nxt = order[(i + k) % len(order)]
            if not s["holed"][nxt][h] and s["strokes"][nxt][h] < STROKE_CAP:
                s["turn"] = nxt
                break
    return s


def is_terminal(state):
    return state["winner"] is not None


def winners(state):
    return [state["winner"]] if state["winner"] is not None else []


def next_seats(state):
    return [] if is_terminal(state) else [state["turn"]]


def render(state, perspective_seat=None):
    hole_no = state["hole_index"] + 1
    lines = [f"Hole {hole_no}/{state['holes']} — seat {state['turn']} to shoot."]
    h = state["hole_index"]
    for p in state["seats"]:
        st = state["strokes"][p][h]
        mark = " (holed)" if state["holed"][p][h] else ""
        lines.append(f"  seat {p}: {st} strokes{mark} "
                     f"@ ({state['balls'][p][0]:.1f}, {state['balls'][p][1]:.1f})")
    totals = {p: sum(s for s, holed in zip(state["strokes"][p], state["holed"][p]))
              for p in state["seats"]}
    lines.append("Totals: " + ", ".join(f"seat {p}: {t}" for p, t in totals.items()))
    return "```\n" + "\n".join(lines) + "\n```"


def fold(moves, config=None):
    state = initial_state(config)
    for move in moves:
        state = apply(state, move)
    return state


# ---- deterministic physics ----

def _simulate(hole, pos, vel):
    """Advance the ball; mutate pos in place. Returns True if holed."""
    walls = hole["walls"]
    cup = hole["cup"]
    t = 0.0
    while t < MAX_T:
        # friction
        damp = max(0.0, 1 - FRICTION * DT)
        vel[0] *= damp
        vel[1] *= damp
        # integrate
        pos[0] += vel[0] * DT
        pos[1] += vel[1] * DT
        # wall bounces
        for (ax, ay, bx, by) in walls:
            _bounce(pos, vel, ax, ay, bx, by)
        # cup capture
        dx, dy = pos[0] - cup[0], pos[1] - cup[1]
        speed = math.hypot(*vel)
        if math.hypot(dx, dy) <= cup[2] and speed <= CAPTURE_SPEED:
            pos[0], pos[1] = cup[0], cup[1]
            return True
        if speed < 0.05:
            return False
        t += DT
    return False


def _bounce(pos, vel, ax, ay, bx, by):
    """Reflect velocity off segment AB if the ball crossed it this step."""
    # Closest point on segment to ball.
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby
    if denom == 0:
        return
    u = ((pos[0] - ax) * abx + (pos[1] - ay) * aby) / denom
    u = max(0.0, min(1.0, u))
    cx, cy = ax + u * abx, ay + u * aby
    dx, dy = pos[0] - cx, pos[1] - cy
    dist = math.hypot(dx, dy)
    R = 0.4  # ball radius
    if dist < R and dist > 1e-9:
        # Push out and reflect.
        nx, ny = dx / dist, dy / dist
        pos[0], pos[1] = cx + nx * R, cy + ny * R
        dot = vel[0] * nx + vel[1] * ny
        if dot < 0:
            vel[0] -= (1 + RESTITUTION) * dot * nx
            vel[1] -= (1 + RESTITUTION) * dot * ny


# ---- course loading ----

_COURSES = None


def _load_course(name):
    global _COURSES
    if _COURSES is None:
        import os
        path = os.path.join(os.path.dirname(__file__), "courses.json")
        with open(path) as f:
            _COURSES = json.load(f)
    return _COURSES[name]["holes"]


def _tee(hole):
    return [float(hole["tee"][0]), float(hole["tee"][1])]


def _leader(state):
    totals = {p: sum(state["strokes"][p]) for p in state["seats"]}
    return min(totals, key=lambda p: totals[p])
