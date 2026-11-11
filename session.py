"""Application actions and information shown beside the board."""

from computer import choose_move
from captured import missing_pieces
from game import (
    copy_position,
    legal_moves,
    move,
    new_position,
    status,
    winner,
)


SAVE_FORMAT = "chess-workshop-save"
SAVE_VERSION = 1


# Legal from the standard starting position under this game's rules.
# Next move: b7-a8, capturing a rook and reaching the last rank.
PROMOTION_SETUP = [
    ("a2", "a4"), ("h7", "h5"),
    ("a4", "a5"), ("h5", "h4"),
    ("a5", "a6"), ("h4", "h3"),
    ("a6", "b7"), ("h3", "g2"),
]


class Session:
    def __init__(self, opponent="human"):
        if opponent not in ("human", "computer"):
            raise ValueError("Unknown opponent")
        self.position = new_position()
        self.notation = []
        # Every move played from the start, as [source, target]. Replaying it rebuilds
        # each earlier position, which is what save/load needs to keep undo possible.
        self.history = []
        # Positions before each played move, oldest first; undo returns to the last one.
        # Kept in step with history; load rebuilds it by replaying the moves.
        self.positions = []
        self.captured = []
        self.opponent = opponent

    def play(self, source, target):
        before = copy_position(self.position)
        label = move(self.position, source, target)
        self.positions.append(before)
        self.notation.append(label)
        self.history.append([source, target])
        self.after_move()

    def undo(self):
        """Take back the last move; against the computer, back to the player's turn.

        The restored position brings back captured pieces and the side to move.
        At the beginning of the game this does nothing.
        """
        while self.positions:
            self.position = self.positions.pop()
            self.notation.pop()
            self.history.pop()
            if self.opponent != "computer" or self.position[1] == "w":
                break
        # The captured display is derived from the board, so refresh it for the
        # restored position; an undone capture leaves the display.
        self.captured = missing_pieces(self.position)

    def save(self):
        """Return everything needed to resume this game, as JSON-ready data."""
        return {
            "format": SAVE_FORMAT,
            "version": SAVE_VERSION,
            "opponent": self.opponent,
            "board": dict(self.position[0]),
            "turn": self.position[1],
            "notation": list(self.notation),
            "history": [list(entry) for entry in self.history],
        }

    def load(self, data):
        """Replace this game with a saved one. On any error the current game is kept."""
        if not isinstance(data, dict) or data.get("format") != SAVE_FORMAT:
            raise ValueError("Not a saved chess game")
        if data.get("version") != SAVE_VERSION:
            raise ValueError("Unsupported save version")
        history = data.get("history")
        if not isinstance(history, list) or not all(
                isinstance(entry, list) and len(entry) == 2 for entry in history):
            raise ValueError("Saved game has an invalid move history")
        restored = Session(data.get("opponent"))
        try:
            for source, target in history:
                restored.play(source, target)
        except ValueError:
            raise ValueError("Saved game contains an illegal move") from None
        if (restored.position[0] != data.get("board")
                or restored.position[1] != data.get("turn")
                or restored.notation != data.get("notation")):
            raise ValueError("Saved game does not match its move history")
        self.__dict__ = restored.__dict__

    def after_move(self):
        self.captured = missing_pieces(self.position)

    def view(self):
        return {
            "board": self.position[0],
            "turn": self.position[1],
            "moves": self.notation,
            "opponent": self.opponent,
            "can_undo": bool(self.positions),
            "status": status(self.position),
            "winner": winner(self.position),
            **self.sidebar(),
        }

    def computer_to_move(self):
        return (self.opponent == "computer" and self.position[1] == "b"
                and status(self.position) not in ("checkmate", "stalemate"))

    def sidebar(self):
        return {"captured": self.captured}

    def dispatch(self, action):
        command = action.get("action")
        if command == "move":
            if self.computer_to_move():
                raise ValueError("Wait for the computer's move")
            self.play(action.get("source"), action.get("target"))
        elif command == "computer-move":
            if not self.computer_to_move():
                raise ValueError("It is not the computer's turn")
            self.play(*choose_move(self.position))
        elif command == "legal":
            return {"targets": legal_moves(self.position, action.get("source"))}
        elif command == "undo":
            self.undo()
        elif command == "save":
            return {"game": self.save()}
        elif command == "load":
            self.load(action.get("game"))
        elif command == "new":
            self.__init__(action.get("opponent", "human"))
        elif command == "promotion-setup":
            self.__init__()
            for source, target in PROMOTION_SETUP:
                self.play(source, target)
        else:
            raise ValueError("Unknown action")
        return self.view()
