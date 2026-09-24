#!/usr/bin/env python3
"""Generate a static tic-tac-toe board widget.

The board does NOT fetch from the relay (chat widget sandboxes block
external network). The agent bakes the current position into the HTML and
pushes a fresh widget whenever the position changes. The widget only
captures taps via the state bridge: setState({selected: i}).

Usage:
    make_board.py ROOM SEAT MARK moves.json > board.html
moves.json: [{"seat":0,"payload":{"cell":7}}, ...]  (only seat/type/payload used)
"""
import json
import sys

HTML = """<div style="box-sizing:border-box;max-width:340px;margin:0 auto;padding:12px;background:var(--hatch-widget-surface);border:1px solid var(--hatch-widget-border);border-radius:12px;box-shadow:var(--hatch-widget-shadow);">
  <div id="s" style="text-align:center;font-weight:600;color:var(--hatch-widget-text);margin-bottom:10px;min-height:1.4em;">__STATUS__</div>
  <div id="g" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;"></div>
  <div style="text-align:center;color:var(--hatch-widget-muted);font-size:12px;margin-top:10px;">Room __ROOM__ &middot; you are __MARK__</div>
</div>
<script>
(function(){
  var BOARD = __BOARD__;
  var ME = __ME__;
  var TURN = __TURN__;
  var WIN = __WIN__;
  var grid = document.getElementById("g");
  var cells = [];
  function paint(sel){
    for (var i = 0; i < 9; i++)
      cells[i].style.outline = (i === sel) ? "3px solid var(--hatch-widget-focus)" : "none";
  }
  for (var i = 0; i < 9; i++) {
    (function(i){
      var b = document.createElement("button");
      b.style.cssText = "aspect-ratio:1/1;font-size:38px;font-weight:700;border-radius:10px;border:1px solid var(--hatch-widget-border);background:var(--hatch-widget-surface-muted);color:var(--hatch-widget-text);touch-action:manipulation;";
      b.textContent = BOARD[i] === " " ? "" : BOARD[i];
      if (BOARD[i] === "X") b.style.color = "var(--hatch-widget-accent)";
      var playable = !WIN && TURN === ME && BOARD[i] === " ";
      b.style.cursor = playable ? "pointer" : "default";
      b.style.opacity = playable ? "1" : "0.85";
      b.addEventListener("click", function(){
        if (!playable) return;
        window.hatchWidget.setState({selected: i});
        paint(i);
        document.getElementById("s").textContent = "Sending your move\\u2026";
      });
      grid.appendChild(b);
      cells.push(b);
    })(i);
  }
  var st = window.hatchWidget.getState({selected: null});
  paint(st.selected);
})();
</script>
"""


def main():
    room, seat, mark, moves_path = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    data = json.load(open(moves_path))
    moves = data["moves"] if isinstance(data, dict) else data
    sys.path.insert(0, __import__("os").path.dirname(__file__))
    import logic
    state = logic.initial_state({})
    for m in moves:
        try:
            state = logic.apply(state, {"seat": m["seat"], "type": m["type"],
                                        "payload": m["payload"]})
        except Exception:
            pass  # ignore illegal/duplicate moves on read, per protocol
    board = state["board"]
    win = logic.winners(state)
    win_mark = ("X" if win == [0] else "O") if win else None
    if logic.is_terminal(state):
        status = "You win!" if win == [seat] else ("Draw." if not win else
                  ("Rival wins." if mark != win_mark else "You win!"))
        turn = -1
    else:
        turn = logic.next_seats(state)[0]
        status = "Your move — tap a cell" if turn == seat else "Rival’s turn…"
    out = HTML.replace("__ROOM__", room).replace("__MARK__", mark)
    out = out.replace("__BOARD__", json.dumps(board))
    out = out.replace("__ME__", str(seat)).replace("__TURN__", str(turn))
    out = out.replace("__WIN__", json.dumps(win_mark))
    out = out.replace("__STATUS__", status)
    sys.stdout.write(out)


if __name__ == "__main__":
    main()
