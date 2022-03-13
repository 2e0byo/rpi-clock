from rpi_clock.lcd import Lcd
import pytest

@pytest.fixture
def lcd(tmp_path):
    l = Lcd(path=tmp_path / "lcd")
    return l

def test_restart_on_init(lcd):
    with lcd.path.open() as f:
        assert f.read() == "\x1b[LI"

def test_write(lcd):
    lcd.write("hello")
    with lcd.path.open() as f:
        assert f.read() == "hello"

def test_goto(lcd):
    lcd.goto(1,1)
    with lcd.path.open() as f:
        assert f.read() == '\x1b[Lx001y001;'

def test_1line(lcd):
    lcd[0] = "short line"
    with lcd.path.open() as f:
        assert f.read() == 'short line      ' 
    lcd[0] = "this is a long line longer than 16 chars"
    with lcd.path.open() as f:
        assert f.read() == "this is a long l"

def test_2lines(lcd, mocker):
    lcd[0] = "short line"
    lcd.goto = mocker.MagicMock()
    with lcd.path.open() as f:
        assert f.read() == 'short line      ' 
    lcd[1] = "line 2"
    lcd.goto.assert_called_with(0, 1)
    with lcd.path.open() as f:
        assert f.read() == "line 2          "

