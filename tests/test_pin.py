import asyncio

import pytest
from rpi_clock.pin import Pin, PinError


def test_uninverted(mocker):
    pi = mocker.MagicMock()
    p = Pin(pi, 6, mode=Pin.OUT)
    p.on()
    pi.write.assert_called_once_with(6, 1)
    p.off()
    pi.write.assert_called_with(6, 0)


def test_inverted(mocker):
    pi = mocker.MagicMock()
    p = Pin(pi, 6, mode=Pin.OUT, inverted=True)
    p.on()
    pi.write.assert_called_once_with(6, 0)
    p.off()
    pi.write.assert_called_with(6, 1)


def test_inverted_call(mocker):
    pi = mocker.MagicMock()
    p = Pin(pi, 6, mode=Pin.OUT, inverted=True)
    p(1)
    pi.write.assert_called_once_with(6, 0)
    p(0)
    pi.write.assert_called_with(6, 1)


def test_uninverted_call(mocker):
    pi = mocker.MagicMock()
    p = Pin(pi, 6, mode=Pin.OUT, inverted=False)
    p(0)
    pi.write.assert_called_once_with(6, 0)
    p(1)
    pi.write.assert_called_with(6, 1)


def test_wrong_mode(mocker):
    pi = mocker.MagicMock()
    p = Pin(pi, 6, mode=Pin.IN, inverted=False)
    with pytest.raises(PinError):
        p(0)


def test_get_val(mocker):
    pi = mocker.MagicMock()
    p = Pin(pi, 6, mode=Pin.IN, inverted=False)
    pi.read.return_value = 6
    assert p() == 6
