import pytest

from rpi_clock.lcd import Lcd


@pytest.fixture
def lcd(tmp_path) -> Lcd:
    return Lcd(path=tmp_path / "lcd")


def test_restart_on_init(tmp_path, mocker):
    mocker.patch("rpi_clock.lcd.Lcd.restart")
    lcd = Lcd(path=tmp_path / "lcd")
    lcd.restart.assert_called_once()


def test_goto(lcd):
    lcd.goto(1, 1)
    with lcd.path.open() as f:
        assert f.read() == "\x1b[Lx001y001;"


def test_1line(lcd):
    lcd[0] = "short line"
    with lcd.path.open() as f:
        assert f.read() == "short line      "
    lcd[0] = "this is a long line longer than 16 chars"
    with lcd.path.open() as f:
        assert f.read() == "this is a long l"


def test_repeat(lcd):
    lcd[0] = "short line"
    now = lcd.path.stat().st_mtime
    lcd[0] = "short line"
    assert lcd.path.stat().st_mtime == now


def test_2lines(lcd, mocker):
    lcd[0] = "short line"
    lcd.goto = mocker.MagicMock()
    with lcd.path.open() as f:
        assert f.read() == "short line      "
    lcd[1] = "line 2"
    lcd.goto.assert_called_with(0, 1)
    with lcd.path.open() as f:
        assert f.read() == "line 2          "
