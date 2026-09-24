"""Battleship — the hidden-state game.

Trust model (see PROTOCOL.md): each player's fleet NEVER leaves their own
computer. Play proceeds in three phases:

1. commit — each seat publishes sha256(canonical_json(ships) + nonce) to the
   relay's commits hash. Nobody can see the fleets, nobody can change them now.
2. play — seats alternate shots. The fleet OWNER declares the result
   (hit/miss/sunk), because only they can know. Shots are public.
3. reveal — each seat publishes {ships, nonce}; anyone can verify the
   commitments and re-check every hit/miss claim. A liar is caught with proof.

Ships: 10x10 grid, cells "A1".."J10". Fleet:
  carrier (5), battleship (4), cruiser (3), submarine (3), destroyer (2).
"""

import hashlib
import json

SIZE = 10
FLEET = {"carrier": 5, "battleship": 4, "cruiser": 3, "submarine": 3,
         "destroyer": 2}


def initial_state(config=None):
    return {
        "phase": "commit",
        "committed": [],       # seats that published a commitment
        "shots": [],           # [{"seat", "cell", "result"}]
        "sunk": {0: [], 1: []},
        "turn": 0,
        "winner": None,
        "revealed": {},        # seat -> {"ships", "nonce"}
    }


# ---- commitments (helpers; the hash itself lives on the relay) ----

def make_commitment(ships, nonce):
    canonical = json.dumps(ships, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((canonical + nonce).encode()).hexdigest()


def verify_reveal(commitment, ships, nonce):
    return make_commitment(ships, nonce) == commitment


# ---- protocol functions ----

def validate(state, move):
    t = move["type"]
    if t == "commit":
        if state["phase"] != "commit":
            raise ValueError("commit phase is over")
        if move["seat"] in state["committed"]:
            raise ValueError("already committed")
    elif t == "shot":
        if state["phase"] != "play":
            raise ValueError("not in play phase")
        if move["seat"] != state["turn"]:
            raise ValueError("not your turn")
        cell = move["payload"]["cell"]
        _check_cell(cell)
        if any(s["cell"] == cell for s in state["shots"]):
            raise ValueError(f"already shot at {cell}")
    elif t == "result":
        if state["phase"] != "play":
            raise ValueError("not in play phase")
        # Only the fleet owner (the one being shot at) may declare.
        last = state["shots"][-1]
        if last.get("result") is not None:
            raise ValueError("result already declared for last shot")
        if move["seat"] == last["seat"]:
            raise ValueError("shooter cannot declare their own result")
        if move["payload"]["result"] not in ("hit", "miss", "sunk"):
            raise ValueError("bad result")
        if move["payload"]["result"] == "sunk" and "ship" not in move["payload"]:
            raise ValueError("sunk must name the ship")
    elif t == "reveal":
        if state["phase"] != "reveal":
            raise ValueError("not in reveal phase")
    else:
        raise ValueError(f"unknown move type: {t}")


def apply(state, move):
    validate(state, move)
    s = json.loads(json.dumps(state))  # deep copy, still pure
    s["sunk"] = {int(k): v for k, v in s["sunk"].items()}  # JSON stringified keys
    s["revealed"] = {int(k): v for k, v in s["revealed"].items()}
    t = move["type"]
    if t == "commit":
        s["committed"].append(move["seat"])
        if len(s["committed"]) == 2:
            s["phase"] = "play"
    elif t == "shot":
        s["shots"].append({"seat": move["seat"],
                           "cell": move["payload"]["cell"],
                           "result": None})
        # turn does NOT advance until the owner declares the result
    elif t == "result":
        s["shots"][-1]["result"] = move["payload"]["result"]
        if move["payload"]["result"] == "sunk":
            s["sunk"][move["seat"]].append(move["payload"]["ship"])
        if len(s["sunk"][move["seat"]]) == len(FLEET):
            s["winner"] = 1 - move["seat"]  # shooter sank everything
            s["phase"] = "reveal"
        else:
            s["turn"] = 1 - s["turn"]
    elif t == "reveal":
        s["revealed"][move["seat"]] = move["payload"]
    return s


def is_terminal(state):
    # Terminal when someone won AND both revealed (so claims are checkable).
    return (state["winner"] is not None
            and len(state["revealed"]) == 2)


def winners(state):
    return [state["winner"]] if state["winner"] is not None else []


def next_seats(state):
    if state["phase"] == "commit":
        return [s for s in (0, 1) if s not in state["committed"]]
    if state["phase"] == "play":
        return [state["turn"]]
    if state["phase"] == "reveal":
        return [s for s in (0, 1) if s not in state["revealed"]]
    return []


def render(state, perspective_seat=None):
    # Each player sees: their shots at the enemy (left) — never the enemy fleet.
    shots = {(s["cell"]): s["result"] for s in state["shots"]
             if s["seat"] == perspective_seat}
    lines = ["    " + " ".join(chr(ord("A") + c) for c in range(SIZE))]
    for r in range(SIZE):
        row = [f"{r + 1:>2} "]
        for c in range(SIZE):
            cell = f"{chr(ord('A') + c)}{r + 1}"
            res = shots.get(cell)
            row.append("X" if res in ("hit", "sunk") else
                       "o" if res == "miss" else
                       "~" if res is None and cell in shots else ".")
        lines.append(" ".join(row))
    head = {"commit": "Waiting for fleet commitments…",
            "play": f"Seat {state['turn']}'s shot.",
            "reveal": "Game over — reveal your fleet to verify."}[state["phase"]]
    if state["winner"] is not None and state["phase"] == "reveal":
        head = f"Seat {state['winner']} sank the fleet! Reveal to verify."
    return "```\n" + "\n".join(lines) + "\n```\n" + head


def fold(moves):
    state = initial_state()
    for move in moves:
        state = apply(state, move)
    return state


def _check_cell(cell):
    if (len(cell) < 2 or len(cell) > 3 or cell[0] not in "ABCDEFGHIJ"
            or not cell[1:].isdigit() or not 1 <= int(cell[1:]) <= 10):
        raise ValueError(f"bad cell: {cell}")
