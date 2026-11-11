"""Application actions and information shown beside the board."""

from typing import Any

from computer import choose_move
from game import (
    Position,
    copy_position,
    legal_moves,
    move,
    new_position,
    promotes,
    status,
    winner,
)

SAVE_FORMAT = "chess-workshop-save"
SAVE_VERSION = 1


# Legal from the standard starting position under this game's rules.
# Next move: b7-a8, capturing a rook and reaching the last rank.
PROMOTION_SETUP = [
    ("a2", "a4"),
    ("h7", "h5"),
    ("a4", "a5"),
    ("h5", "h4"),
    ("a5", "a6"),
    ("h4", "h3"),
    ("a6", "b7"),
    ("h3", "g2"),
]


def checked_moves(value: object) -> list[list[str]]:
    """Moves from a save file, in history's format; their legality is checked later."""
    if not isinstance(value, list) or not all(
        isinstance(entry, list) and len(entry) in (2, 3) for entry in value
    ):
        raise ValueError("Saved game has an invalid move history")
    return value


class Session:
    def __init__(self, opponent: str = "human") -> None:
        self.reset(opponent)

    def reset(self, opponent: str = "human") -> None:
        """Start a new game, clearing undo and redo."""
        if opponent not in ("human", "computer"):
            raise ValueError("Unknown opponent")
        self.position = new_position()
        self.notation: list[str] = []
        # Every move played from the start, as [source, target] plus the promotion piece
        # when a pawn promotes. Replaying it rebuilds each earlier position, which is
        # what save/load needs to keep undo possible.
        self.history: list[list[str]] = []
        # Before each played move, oldest first: the position and the captured pieces.
        # Undo returns to the last one. Kept in step with history; load rebuilds it by
        # replaying the moves.
        self.snapshots: list[tuple[Position, list[str]]] = []
        # Pieces captured so far, as they were when taken (a promoted piece keeps its
        # promoted type; promotion alone is not a capture).
        self.captured: list[str] = []
        # Undone moves in history's format, the next one to redo last. Playing that same
        # move keeps the rest of the continuation; any other move discards it.
        self.redo_moves: list[list[str]] = []
        self.opponent = opponent

    def play(self, source: str, target: str, promotion: str | None = None) -> None:
        before = (copy_position(self.position), list(self.captured))
        taken = self.position[0].get(target)
        label = move(self.position, source, target, promotion)
        entry = [source, target] + ([promotion] if promotion else [])
        self.snapshots.append(before)
        if taken:
            self.captured.append(taken)
        self.notation.append(label)
        self.history.append(entry)
        if self.redo_moves and self.redo_moves[-1] == entry:
            self.redo_moves.pop()
        else:
            self.redo_moves.clear()
        self.after_move()

    def undo(self) -> None:
        """Take back the last move; against the computer, back to the player's turn.

        The restored position brings back captured pieces and the side to move.
        At the beginning of the game this does nothing.
        """
        while self.snapshots:
            self.position, self.captured = self.snapshots.pop()
            self.notation.pop()
            self.redo_moves.append(self.history.pop())
            if self.opponent != "computer" or self.position[1] == "w":
                break

    def redo(self) -> None:
        """Play the most recently undone move again. With nothing to redo, do nothing.

        Replaying it restores any capture or promotion. Against the computer only the
        player's move is redone; the computer then chooses its reply afresh, and the
        old continuation survives only if it picks the same move.
        """
        if self.redo_moves:
            self.play(*self.redo_moves[-1])

    def save(self) -> dict[str, Any]:
        """Return everything needed to resume this game, as JSON-ready data."""
        return {
            "format": SAVE_FORMAT,
            "version": SAVE_VERSION,
            "opponent": self.opponent,
            "board": dict(self.position[0]),
            "turn": self.position[1],
            "notation": list(self.notation),
            "history": [list(entry) for entry in self.history],
            "redo": [list(entry) for entry in self.redo_moves],
        }

    def load(self, data: object) -> None:
        """Replace this game with a saved one. On any error the current game is kept."""
        if not isinstance(data, dict) or data.get("format") != SAVE_FORMAT:
            raise ValueError("Not a saved chess game")
        if data.get("version") != SAVE_VERSION:
            raise ValueError("Unsupported save version")
        history = checked_moves(data.get("history"))
        # Saves made before redo existed have no "redo" entry.
        redo = checked_moves(data.get("redo", []))
        # A missing opponent fails Session's own check.
        restored = Session(data.get("opponent", ""))
        continuation = Session(data.get("opponent", ""))
        try:
            for entry in history:
                restored.play(*entry)
            # The redo moves must be playable in order after the history.
            for entry in history + redo[::-1]:
                continuation.play(*entry)
        except (ValueError, TypeError):
            raise ValueError("Saved game contains an illegal move") from None
        restored.redo_moves = [list(entry) for entry in redo]
        if (
            restored.position[0] != data.get("board")
            or restored.position[1] != data.get("turn")
            or restored.notation != data.get("notation")
        ):
            raise ValueError("Saved game does not match its move history")
        self.__dict__ = restored.__dict__

    def after_move(self) -> None:
        pass

    def view(self) -> dict[str, Any]:
        return {
            "board": self.position[0],
            "turn": self.position[1],
            "moves": self.notation,
            "opponent": self.opponent,
            "can_undo": bool(self.snapshots),
            "can_redo": bool(self.redo_moves) and not self.computer_to_move(),
            "status": status(self.position),
            "winner": winner(self.position),
            **self.sidebar(),
        }

    def computer_to_move(self) -> bool:
        return (
            self.opponent == "computer"
            and self.position[1] == "b"
            and status(self.position) not in ("checkmate", "stalemate")
        )

    def sidebar(self) -> dict[str, Any]:
        return {"captured": sorted(self.captured)}

    def dispatch(self, action: dict[str, Any]) -> dict[str, Any]:
        command = action.get("action")
        if command == "move":
            if self.computer_to_move():
                raise ValueError("Wait for the computer's move")
            self.play(
                action.get("source", ""),
                action.get("target", ""),
                action.get("promotion"),
            )
        elif command == "computer-move":
            if not self.computer_to_move():
                raise ValueError("It is not the computer's turn")
            choice = choose_move(self.position)
            if choice is None:  # computer_to_move() has ruled this out
                raise ValueError("The computer has no move")
            self.play(*choice)
        elif command == "legal":
            source = action.get("source", "")
            targets = legal_moves(self.position, source)
            return {
                "targets": targets,
                "promotions": [
                    t for t in targets if promotes(self.position, source, t)
                ],
            }
        elif command == "undo":
            self.undo()
        elif command == "redo":
            if self.computer_to_move():
                raise ValueError("Wait for the computer's move")
            self.redo()
        elif command == "save":
            return {"game": self.save()}
        elif command == "load":
            self.load(action.get("game"))
        elif command == "new":
            self.reset(action.get("opponent", "human"))
        elif command == "promotion-setup":
            self.reset()
            for source, target in PROMOTION_SETUP:
                self.play(source, target)
        else:
            raise ValueError("Unknown action")
        return self.view()
