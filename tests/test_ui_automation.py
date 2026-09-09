import subprocess

from bnet_umu.core import ui_automation


class FakeClock:
    """Deterministic stand-in for time.monotonic()/time.sleep() so tests
    don't actually wait in real time."""

    def __init__(self):
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_xdotool_available_true(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/xdotool")
    assert ui_automation.xdotool_available() is True


def test_xdotool_available_false(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert ui_automation.xdotool_available() is False


def test_find_window_parses_first_id(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="123\n456\n", stderr=""),
    )
    assert ui_automation.find_window("Battle.net") == "123"


def test_find_window_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="", stderr=""),
    )
    assert ui_automation.find_window("Battle.net") is None


def test_wait_for_window_returns_as_soon_as_found(monkeypatch):
    calls = iter([None, None, "999"])
    monkeypatch.setattr(ui_automation, "find_window", lambda title: next(calls))
    clock = FakeClock()

    result = ui_automation.wait_for_window(
        "x", timeout=10, poll_interval=1, sleep_fn=clock.sleep, clock=clock.clock
    )
    assert result == "999"


def test_wait_for_window_times_out(monkeypatch):
    monkeypatch.setattr(ui_automation, "find_window", lambda title: None)
    clock = FakeClock()

    result = ui_automation.wait_for_window(
        "x", timeout=5, poll_interval=1, sleep_fn=clock.sleep, clock=clock.clock
    )
    assert result is None
    assert clock.now >= 5


def test_close_login_window_returns_false_when_xdotool_missing(monkeypatch):
    monkeypatch.setattr(ui_automation, "xdotool_available", lambda: False)
    messages = []

    result = ui_automation.close_login_window(log=messages.append)

    assert result is False
    assert any("xdotool not found" in m for m in messages)


def test_close_login_window_closes_and_returns_true_when_found(monkeypatch):
    monkeypatch.setattr(ui_automation, "xdotool_available", lambda: True)
    monkeypatch.setattr(ui_automation, "wait_for_window", lambda *a, **k: "login-1")
    closed = []
    monkeypatch.setattr(ui_automation, "close_window", lambda wid: closed.append(wid))

    result = ui_automation.close_login_window(log=lambda m: None, sleep_fn=lambda s: None)

    assert result is True
    assert closed == ["login-1"]


def test_close_login_window_returns_false_when_window_never_appears(monkeypatch):
    monkeypatch.setattr(ui_automation, "xdotool_available", lambda: True)
    monkeypatch.setattr(ui_automation, "wait_for_window", lambda *a, **k: None)
    messages = []

    result = ui_automation.close_login_window(log=messages.append, sleep_fn=lambda s: None)

    assert result is False
    assert any("Couldn't find the login window" in m for m in messages)
