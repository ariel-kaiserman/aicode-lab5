import json
from typing import Any

import pytest

from session import SAVE_FORMAT, SAVE_VERSION, Session


def played(opponent: str = "human") -> Session:
    session = Session(opponent)
    for source, target in [("e2", "e4"), ("d7", "d5"), ("e4", "d5")]:
        session.play(source, target)
    return session


def test_round_trip_restores_the_game_and_opponent() -> None:
    session = Session("computer")
    session.play("e2", "e4")
    saved = json.loads(json.dumps(session.dispatch({"action": "save"})["game"]))
    assert saved["format"] == SAVE_FORMAT and saved["version"] == SAVE_VERSION
    fresh = Session()
    view = fresh.dispatch({"action": "load", "game": saved})
    assert view == session.view()
    assert fresh.opponent == "computer"
    assert fresh.computer_to_move()


def test_load_then_undo_reaches_moves_made_before_saving() -> None:
    session = played()
    fresh = Session()
    fresh.load(session.save())
    fresh.undo()
    fresh.undo()
    fresh.undo()
    assert fresh.view()["moves"] == []
    assert fresh.view()["can_redo"]


def corrupt(change: str) -> dict[str, Any]:
    """A valid save with one thing wrong."""
    saved = played().save()
    if change == "format":
        saved["format"] = "something-else"
    elif change == "version":
        saved["version"] = SAVE_VERSION + 1
    elif change == "history":
        saved["history"] = "e2e4"
    elif change == "entry":
        saved["history"][0] = ["e2", "e4", "Q", "extra"]
    elif change == "illegal":
        saved["history"][0] = ["e2", "e5"]
    elif change == "not a square":
        saved["history"][0] = [2, 4]
    elif change == "board":
        saved["board"]["a1"] = "wQ"
    elif change == "turn":
        saved["turn"] = "w"
    elif change == "notation":
        saved["notation"][0] = "e2-e3"
    elif change == "opponent":
        del saved["opponent"]
    return saved


@pytest.mark.parametrize(
    "change,error",
    [
        ("format", "Not a saved chess game"),
        ("version", "Unsupported save version"),
        ("history", "invalid move history"),
        ("entry", "invalid move history"),
        ("illegal", "illegal move"),
        ("not a square", "illegal move"),
        ("board", "does not match"),
        ("turn", "does not match"),
        ("notation", "does not match"),
        ("opponent", "Unknown opponent"),
    ],
)
def test_bad_save_is_rejected_and_the_game_kept(change: str, error: str) -> None:
    current = Session()
    current.play("g1", "f3")
    before = json.loads(json.dumps(current.view()))
    with pytest.raises(ValueError, match=error):
        current.load(corrupt(change))
    assert current.view() == before


@pytest.mark.parametrize("game", [None, [], "saved", 3])
def test_load_rejects_data_that_is_not_a_save(game: object) -> None:
    with pytest.raises(ValueError, match="Not a saved chess game"):
        Session().dispatch({"action": "load", "game": game})
