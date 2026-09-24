#!/usr/bin/env python3
"""doctor.py — pre-game self-test for muse-casual-games (tic-tac-toe).

Run BEFORE playing, with the handle you will play as:

    python3 doctor.py ROOM HANDLE

Your seat is DERIVED from the room meta — never pass it by hand. A wrong
seat is the classic misconfiguration (board shows the wrong turn, taps get
ignored), and this script exists to catch it before move one.

Checks:
  1. relay reachable
  2. room exists (warns if already finished)
  3. HANDLE owns a seat in the room
  4. the room's pinned game code is fetchable from the relay
  5. the move log folds cleanly through logic.py (invalid entries are
     reported as warnings, not fatal — e.g. a double-posted tap)
  6. make_board.py renders a board for YOUR seat whose status line agrees
     with the folded position

Exit 0: safe to play. Exit 1: fix the FAIL lines first.
Network calls retry with backoff (the relay connection has been flaky).
Stdlib only.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

RELAY = "https://relay.onthe1.app"
GAME = "tic-tac-toe"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import logic  # noqa: E402

results = []  # (ok: True/False/"warn", label, detail)


def note(ok, label, detail=""):
    results.append((ok, label, detail))


def get_bytes(path, tries=4):
    last = None
    for a in range(tries):
        try:
            with urllib.request.urlopen(RELAY + path, timeout=30) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - transient network, retry
            last = e
            time.sleep(2 * (a + 1))
    raise last


def get(path, tries=4):
    return json.loads(get_bytes(path, tries).decode())


def main():
    if len(sys.argv) != 3:
        print("usage: doctor.py ROOM HANDLE", file=sys.stderr)
        return 2
    room, handle = sys.argv[1], sys.argv[2]

    # 1. relay reachable
    try:
        h = get("/health", tries=2)
        note(h.get("ok") is True, "relay reachable",
             "" if h.get("ok") else f"unexpected: {h}")
    except Exception as e:
        note(False, "relay reachable", f"{type(e).__name__}: {e}")
        return finish()

    # 2. room exists
    try:
        meta = get(f"/v0/rooms/{room}")
    except Exception as e:
        note(False, "room exists", f"{type(e).__name__}: {e}")
        return finish()
    note(True, "room exists",
         f"game={meta.get('game')} version_sha={meta.get('version_sha')}")
    if meta.get("status") == "finished":
        note("warn", "room not finished", "room is finished — checks still run")
    else:
        note(True, "room not finished", f"status={meta.get('status')}")
    if meta.get("game") != GAME:
        note(False, "game matches", f"room is {meta.get('game')}, not {GAME}")
        return finish()
    version = meta["version_sha"]

    # 3. seat ownership — derived, never assumed
    seats = meta.get("seats", [])
    if handle not in seats:
        note(False, "handle owns a seat",
             f"{handle} not in room seats {seats}")
        return finish()
    seat = seats.index(handle)
    mark = "X" if seat == 0 else "O"
    note(True, "handle owns a seat", f"{handle} is seat {seat} ({mark})")

    # 4. pinned code fetchable
    code_ok = True
    for name in ("logic.py", "make_board.py", "manifest.json"):
        try:
            body = get_bytes(f"/v0/code/{version}/games/{GAME}/{name}")
            note(True, f"code fetch: {name}", f"{len(body)} bytes")
        except Exception as e:
            detail = f"{type(e).__name__}: {e}"
            if "404" in detail:
                detail += (f" — version {version[:12]} predates this file; "
                           "the room needs a newer game version")
            note(False, f"code fetch: {name}", detail)
            code_ok = False
    if not code_ok:
        return finish()
    print("  (trust check is yours: verify the release tag signature before "
          "first run)", flush=True)

    # 5. fold the log
    try:
        data = get(f"/v0/rooms/{room}/moves")
    except Exception as e:
        note(False, "move log readable", f"{type(e).__name__}: {e}")
        return finish()
    moves = data["moves"] if isinstance(data, dict) else data
    state = logic.initial_state({})
    bad = 0
    for i, m in enumerate(moves):
        try:
            state = logic.apply(state, {"seat": m["seat"], "type": m["type"],
                                        "payload": m["payload"]})
        except Exception as e:
            bad += 1
            note("warn", f"log entry {i} invalid",
                 f"seat {m.get('seat')} {m.get('type')} {m.get('payload')}: "
                 f"{e} — skipped")
    note(True, "move log folds",
         f"{len(moves) - bad}/{len(moves)} valid, {bad} skipped")
    if logic.is_terminal(state):
        w = logic.winners(state)
        note(True, "position",
             "terminal: " + ("draw" if not w else
                             f"{'X' if w == [0] else 'O'} wins"))
    else:
        turn = logic.next_seats(state)[0]
        note(True, "position",
             f"{len(moves) - bad} moves in, "
             + ("YOUR move (seat %d)" % seat if turn == seat
                else f"waiting on rival (seat {turn})"))

    # 6. board renders for MY seat and agrees with the fold
    moves_path = os.path.join(HERE, ".doctor-moves.json")
    try:
        with open(moves_path, "w") as f:
            json.dump(moves, f)
        out = subprocess.run(
            [sys.executable, os.path.join(HERE, "make_board.py"),
             room, str(seat), mark, moves_path],
            capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            note(False, "board renders", out.stderr.strip()[:200])
            return finish()
        html = out.stdout
        if logic.is_terminal(state):
            w = logic.winners(state)
            expect = ("Draw." if not w else
                      "You win!" if w == [seat] else "Rival wins.")
        else:
            expect = ("Your move" if logic.next_seats(state)[0] == seat
                      else "Rival")
        if expect in html and mark in html:
            note(True, "board agrees with position",
                 f"status shows '{expect}', mark {mark}")
        else:
            note(False, "board agrees with position",
                 f"expected '{expect}' in rendered board — "
                 "wrong seat or stale renderer?")
    except Exception as e:
        note(False, "board renders", f"{type(e).__name__}: {e}")
    finally:
        try:
            os.unlink(moves_path)
        except OSError:
            pass

    return finish()


def finish():
    print()
    failed = warned = 0
    for ok, label, detail in results:
        tag = "PASS" if ok is True else ("WARN" if ok == "warn" else "FAIL")
        if ok == "warn":
            warned += 1
        elif ok is not True:
            failed += 1
        line = f"[{tag}] {label}"
        if detail:
            line += f" — {detail}"
        print(line)
    print()
    if failed:
        print(f"DO NOT PLAY: {failed} check(s) failed"
              + (f", {warned} warning(s)." if warned else "."))
        return 1
    print("Safe to play."
          + (f" ({warned} warning(s) — see above.)" if warned else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
