import pytest

import session as session_module
from computer import evaluate
from game import Position
from session import Session


@pytest.mark.parametrize("action", [{"action": "fly"}, {}])
def test_unknown_action(action: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="Unknown action"):
        Session().dispatch(action)


def test_computer_without_a_move_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_module, "choose_move", lambda position: None)
    session = Session("computer")
    session.play("e2", "e4")
    with pytest.raises(ValueError, match="no move"):
        session.dispatch({"action": "computer-move"})
    assert session.view()["moves"] == ["e2-e4"]


def test_stalemate_scores_zero_whatever_the_material() -> None:
    position: Position = [{"a8": "bK", "b6": "wQ", "c1": "wK"}, "b"]
    assert evaluate(position, "w") == 0
    assert evaluate(position, "b") == 0
