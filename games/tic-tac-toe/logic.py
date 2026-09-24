"""Tic-tac-toe — reference implementation of the muse-games protocol.

Pure functions only: no I/O, no clock, no randomness. The agent folds the
room's move log through apply() to get current state, and calls render()
to show it in chat.
"""

EMPTY = " "
LINES = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # cols
    (0, 4, 8), (2, 4, 6),             # diags
)


def initial_state(config=None):
    return {"board": [EMPTY] * 9, "turn": 0, "winner": None}


def validate(state, move):
    if move["type"] != "place":
        raise ValueError(f"unknown move type: {move['type']}")
    cell = move["payload"]["cell"]
    if not isinstance(cell, int) or not 0 <= cell <= 8:
        raise ValueError(f"cell out of range: {cell}")
    if state["board"][cell] != EMPTY:
        raise ValueError(f"cell {cell} already taken")
    if move["seat"] != state["turn"]:
        raise ValueError(f"not seat {move['seat']}'s turn")
    if state["winner"] is not None:
        raise ValueError("game is over")


def apply(state, move):
    validate(state, move)
    board = state["board"][:]
    board[move["payload"]["cell"]] = "X" if move["seat"] == 0 else "O"
    winner = _winner(board)
    if winner is None and all(c != EMPTY for c in board):
        winner = "draw"
    return {"board": board, "turn": 1 - state["turn"], "winner": winner}


def is_terminal(state):
    return state["winner"] is not None


def winners(state):
    if state["winner"] == "draw" or state["winner"] is None:
        return []
    return [0] if state["winner"] == "X" else [1]


def next_seats(state):
    return [] if is_terminal(state) else [state["turn"]]


def render(state, perspective_seat=None):
    b = state["board"]
    rows = []
    for r in range(3):
        rows.append(" " + " | ".join(b[r * 3 + c] for c in range(3)))
    board = "\n---+---+---\n".join(rows)
    status = "Game over: "
    if state["winner"] == "draw":
        status += "draw."
    elif state["winner"]:
        status += f"{state['winner']} wins!"
    else:
        mark = "X" if state["turn"] == 0 else "O"
        status = f"{mark} to play."
    return f"```\n{board}\n```\n{status}"


def _winner(board):
    for a, b_, c in LINES:
        if board[a] != EMPTY and board[a] == board[b_] == board[c]:
            return board[a]
    return None


def fold(moves):
    """Fold a list of move dicts (in log order) into the current state."""
    state = initial_state()
    for move in moves:
        state = apply(state, move)
    return state
