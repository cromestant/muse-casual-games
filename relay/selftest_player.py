#!/usr/bin/env python3
"""Self-test player: polls the relay, folds the log, moves when it's our turn.

Usage: selftest_player.py <room_code> <seat> <handle>
Exits 0 when the game is terminal, 1 on timeout/error.
"""
import json
import os
import subprocess
import sys
import time

REPO = os.path.expanduser("~/workspace/muse-games")
sys.path.insert(0, os.path.join(REPO, "games", "tic-tac-toe"))
import logic  # noqa: E402

VIA = os.path.join(REPO, "relay", "via_ssh.sh")


def r(*args):
    p = subprocess.run(["bash", VIA, *args], capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError(f"relay error: {p.stderr.strip()}")
    return p.stdout


def read_moves(room):
    out = r("lrange", f"mg:room:{room}:moves", "0", "-1").strip()
    moves = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            moves.append(json.loads(line))
        except json.JSONDecodeError:
            raise RuntimeError(f"corrupt move-log line in {room}: {line!r}")
    return moves


def push_move(room, envelope):
    r("rpush", f"mg:room:{room}:moves", json.dumps(envelope, separators=(",", ":")))


def pick_move(state, seat):
    board = state["board"]
    mark = "X" if seat == 0 else "O"
    omark = "O" if seat == 0 else "X"
    empties = [i for i, c in enumerate(board) if c == " "]
    for c in empties:  # win if possible
        b = board[:]
        b[c] = mark
        if logic._winner(b) == mark:
            return c
    for c in empties:  # block if needed
        b = board[:]
        b[c] = omark
        if logic._winner(b) == omark:
            return c
    return empties[0]


def main():
    room, seat, handle = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    for _ in range(120):
        moves = read_moves(room)
        state = logic.fold(moves)
        if logic.is_terminal(state):
            r("hset", f"mg:room:{room}", "status", "finished")
            print(logic.render(state), flush=True)
            print(
                f"GAME_OVER winner_seats={logic.winners(state)} "
                f"moves={len(moves)} handle={handle}",
                flush=True,
            )
            return
        if state["turn"] == seat:
            cell = pick_move(state, seat)
            move = {"seat": seat, "type": "place", "payload": {"cell": cell}}
            logic.validate(state, move)  # protocol: validate locally before append
            push_move(room, {**move, "handle": handle, "ts": int(time.time())})
            print(f"MOVED seat={seat} cell={cell} total_moves={len(moves) + 1}", flush=True)
        time.sleep(4)
    print("TIMEOUT: game did not finish", flush=True)
    sys.exit(1)


main()
