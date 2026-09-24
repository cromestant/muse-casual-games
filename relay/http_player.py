#!/usr/bin/env python3
"""HTTP relay player: polls the public API, folds the log, moves on our turn.

Usage: http_player.py <base_url> <room_code> <handle> <secret> <seat>
Exits 0 when the game is terminal, 1 on timeout/error.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

REPO = os.path.expanduser("~/workspace/muse-games")
sys.path.insert(0, os.path.join(REPO, "games", "tic-tac-toe"))
import logic  # noqa: E402


def call(method, base, path, body=None, tries=4):
    data = json.dumps(body).encode() if body is not None else None
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(base + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()[:200]
        except Exception as e:  # transient drops (proxy/relay hiccup): retry
            last = e
            time.sleep(3)
    raise RuntimeError(f"{method} {path} failed after {tries} tries: {last}")


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
    base, code, handle, secret, seat = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
    auth = {"handle": handle, "secret": secret}
    for _ in range(200):
        st, log = call("GET", base, f"/v0/rooms/{code}/moves")
        if st != 200:
            raise RuntimeError(f"read moves failed: {st} {log}")
        state = logic.fold(log["moves"])
        if logic.is_terminal(state):
            st, _ = call("POST", base, f"/v0/rooms/{code}/finish", auth)
            print(logic.render(state), flush=True)
            print(f"GAME_OVER winner_seats={logic.winners(state)} "
                  f"moves={len(log['moves'])} handle={handle}", flush=True)
            return
        if state["turn"] == seat:
            cell = pick_move(state, seat)
            move = {"seat": seat, "type": "place", "payload": {"cell": cell}}
            logic.validate(state, move)  # validate locally before sending
            st, resp = call("POST", base, f"/v0/rooms/{code}/moves",
                            {**auth, **move})
            if st != 200:
                raise RuntimeError(f"post move failed: {st} {resp}")
            print(f"MOVED seat={seat} cell={cell} "
                  f"total_moves={len(log['moves']) + 1}", flush=True)
        time.sleep(5)
    print("TIMEOUT: game did not finish", flush=True)
    sys.exit(1)


main()
