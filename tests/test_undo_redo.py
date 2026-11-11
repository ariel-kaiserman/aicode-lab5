import json
from typing import Any

import pytest

import session as session_module
from game import new_position
from session import Session

CAPTURE = [("e2", "e4"), ("d7", "d5"), ("e4", "d5")]


def play_all(session: Session, moves: list[tuple[str, str]]) -> None:
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def frozen_view(session: Session) -> dict[str, Any]:
    """A copy of the view; view() shares lists that later moves change."""
    result: dict[str, Any] = json.loads(json.dumps(session.view()))
    return result


def round_trip(session: Session) -> Session:
    """Save, pass through JSON as the browser does, and load into a fresh session."""
    saved = json.loads(json.dumps(session.dispatch({"action": "save"})["game"]))
    fresh = Session()
    fresh.dispatch({"action": "load", "game": saved})
    return fresh


def test_undo_and_redo_at_the_edges_do_nothing() -> None:
    session = Session()
    view = session.dispatch({"action": "undo"})
    assert view["moves"] == [] and not view["can_undo"] and not view["can_redo"]
    assert session.position == new_position()
    play_all(session, CAPTURE)
    view = session.dispatch({"action": "redo"})
    assert view["moves"] == ["e2-e4", "d7-d5", "e4xd5"]
    assert not view["can_redo"]


def test_undo_restores_capture_side_and_notation() -> None:
    session = Session()
    play_all(session, CAPTURE)
    assert session.view()["captured"] == ["bP"]
    view = session.dispatch({"action": "undo"})
    assert view["captured"] == []
    assert view["turn"] == "w"
    assert view["moves"] == ["e2-e4", "d7-d5"]
    assert view["board"]["d5"] == "bP" and view["board"]["e4"] == "wP"
    assert view["can_redo"]


def test_redo_restores_a_capture() -> None:
    session = Session()
    play_all(session, CAPTURE)
    after = frozen_view(session)
    session.dispatch({"action": "undo"})
    session.dispatch({"action": "undo"})
    session.dispatch({"action": "redo"})
    view = session.dispatch({"action": "redo"})
    assert view == after
    assert view["captured"] == ["bP"]


def test_redo_restores_promotion_with_the_chosen_piece() -> None:
    session = Session()
    session.dispatch({"action": "promotion-setup"})
    session.dispatch(
        {"action": "move", "source": "b7", "target": "a8", "promotion": "N"}
    )
    after = frozen_view(session)
    assert after["moves"][-1] == "b7xa8=N"
    session.dispatch({"action": "undo"})
    assert session.view()["board"]["b7"] == "wP"
    # The setup's a6xb7 and h3xg2 captures remain; the undone b7xa8 capture is gone.
    assert session.view()["captured"] == ["bP", "wP"]
    view = session.dispatch({"action": "redo"})
    assert view == after
    assert view["board"]["a8"] == "wN"
    assert view["captured"] == ["bP", "bR", "wP"]


def test_promotion_alone_is_not_a_capture_and_captures_keep_their_type() -> None:
    session = Session()
    session.position = [{"a1": "wK", "h6": "bK", "d7": "wP", "b8": "bR"}, "w"]
    session.play("d7", "d8", "Q")
    assert session.view()["captured"] == []
    session.play("b8", "d8")
    assert session.view()["captured"] == ["wQ"]
    session.undo()
    assert session.view()["captured"] == []
    session.redo()
    assert session.view()["captured"] == ["wQ"]


def test_a_different_move_discards_the_redo_continuation() -> None:
    session = Session()
    play_all(session, CAPTURE)
    session.dispatch({"action": "undo"})
    session.dispatch({"action": "undo"})
    view = session.dispatch({"action": "move", "source": "e7", "target": "e5"})
    assert not view["can_redo"]
    assert view["moves"] == ["e2-e4", "e7-e5"]
    view = session.dispatch({"action": "redo"})
    assert view["moves"] == ["e2-e4", "e7-e5"]


def test_replaying_the_undone_move_keeps_the_continuation() -> None:
    session = Session()
    play_all(session, CAPTURE)
    session.dispatch({"action": "undo"})
    session.dispatch({"action": "undo"})
    play_all(session, [("d7", "d5")])
    view = session.dispatch({"action": "redo"})
    assert view["moves"] == ["e2-e4", "d7-d5", "e4xd5"]


def test_an_illegal_move_keeps_the_redo_continuation() -> None:
    session = Session()
    play_all(session, CAPTURE)
    session.dispatch({"action": "undo"})
    with pytest.raises(ValueError):
        session.dispatch({"action": "move", "source": "e4", "target": "e6"})
    assert session.view()["can_redo"]


def test_undo_save_load_redo() -> None:
    session = Session()
    play_all(session, CAPTURE)
    after = frozen_view(session)
    session.dispatch({"action": "undo"})
    session.dispatch({"action": "undo"})
    loaded = round_trip(session)
    assert loaded.view() == session.view()
    loaded.dispatch({"action": "redo"})
    assert loaded.dispatch({"action": "redo"}) == after
    loaded.dispatch({"action": "undo"})
    assert loaded.view()["moves"] == ["e2-e4", "d7-d5"]


def test_save_load_preserves_a_promotion_in_redo() -> None:
    session = Session()
    session.dispatch({"action": "promotion-setup"})
    session.dispatch(
        {"action": "move", "source": "b7", "target": "a8", "promotion": "B"}
    )
    after = frozen_view(session)
    session.dispatch({"action": "undo"})
    loaded = round_trip(session)
    assert loaded.dispatch({"action": "redo"}) == after


def test_load_accepts_a_save_without_redo() -> None:
    session = Session()
    play_all(session, CAPTURE)
    saved = session.save()
    del saved["redo"]
    fresh = Session()
    fresh.load(saved)
    assert fresh.view() == session.view()


@pytest.mark.parametrize(
    "redo",
    [
        "e2",  # not a list
        [["e2"]],  # malformed entry
        [["e2", "e5"]],  # illegal continuation
    ],
)
def test_load_rejects_a_bad_redo_and_keeps_the_game(redo: object) -> None:
    session = Session()
    play_all(session, CAPTURE)
    saved = session.save()
    saved["redo"] = redo
    current = Session()
    play_all(current, [("g1", "f3")])
    before = frozen_view(current)
    with pytest.raises(ValueError):
        current.load(saved)
    assert current.view() == before


def test_new_game_clears_undo_and_redo() -> None:
    session = Session()
    play_all(session, CAPTURE)
    session.dispatch({"action": "undo"})
    view = session.dispatch({"action": "new"})
    assert not view["can_undo"] and not view["can_redo"]
    assert view["captured"] == [] and view["moves"] == []
    assert session.position == new_position()


def scripted_computer(
    monkeypatch: pytest.MonkeyPatch, replies: list[tuple[str, str]]
) -> None:
    """Make the computer play the given replies in order."""
    queue = list(replies)
    monkeypatch.setattr(session_module, "choose_move", lambda position: queue.pop(0))


def test_computer_undo_takes_back_the_reply_and_the_move(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripted_computer(monkeypatch, [("e7", "e5")])
    session = Session("computer")
    play_all(session, [("e2", "e4")])
    session.dispatch({"action": "computer-move"})
    view = session.dispatch({"action": "undo"})
    assert view["moves"] == [] and view["turn"] == "w"
    assert view["can_redo"]


def test_computer_redo_replays_only_the_player_move(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripted_computer(monkeypatch, [("e7", "e5"), ("c7", "c5")])
    session = Session("computer")
    play_all(session, [("e2", "e4")])
    session.dispatch({"action": "computer-move"})
    session.dispatch({"action": "undo"})
    view = session.dispatch({"action": "redo"})
    assert view["moves"] == ["e2-e4"]
    assert view["turn"] == "b"
    assert session.computer_to_move()
    assert not view["can_redo"]
    with pytest.raises(ValueError):
        session.dispatch({"action": "redo"})
    view = session.dispatch({"action": "computer-move"})
    assert view["moves"] == ["e2-e4", "c7-c5"]
    assert not view["can_redo"]


def test_computer_repeating_its_reply_keeps_the_continuation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripted_computer(monkeypatch, [("e7", "e5"), ("b8", "c6"), ("e7", "e5")])
    session = Session("computer")
    play_all(session, [("e2", "e4")])
    session.dispatch({"action": "computer-move"})
    play_all(session, [("g1", "f3")])
    session.dispatch({"action": "computer-move"})
    session.dispatch({"action": "undo"})
    session.dispatch({"action": "undo"})
    session.dispatch({"action": "redo"})
    view = session.dispatch({"action": "computer-move"})
    assert view["can_redo"]
    view = session.dispatch({"action": "redo"})
    assert view["moves"] == ["e2-e4", "e7-e5", "g1-f3"]
    assert session.computer_to_move()


def test_computer_redo_survives_save_and_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripted_computer(monkeypatch, [("e7", "e5"), ("d7", "d6")])
    session = Session("computer")
    play_all(session, [("e2", "e4")])
    session.dispatch({"action": "computer-move"})
    session.dispatch({"action": "undo"})
    loaded = round_trip(session)
    assert loaded.opponent == "computer"
    view = loaded.dispatch({"action": "redo"})
    assert view["moves"] == ["e2-e4"] and loaded.computer_to_move()
    view = loaded.dispatch({"action": "computer-move"})
    assert view["moves"] == ["e2-e4", "d7-d6"]
