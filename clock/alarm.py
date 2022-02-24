from logging import getLogger
from datetime import datetime, time, date, timedelta


class AlarmError(Exception):
    pass


class AlarmClock:
    instances = []

    def __init__(self):
        self.name = f"AlarmClock {len(self.instances) + 1}"
        self.instances.append(self.name)
        self._logger = getLogger(self.name)
        self._alarm_time = None
        self._nominal_alarm_time = None
        self._alarm_enabled = False
        self._sound = False
        self._sounding = False
        self._old_alarm_time = None

    def calculate_alarm(self, nominal: time):
        """Apply transformation to alarm time, e.g. for fading."""
        self._alarm_time = nominal

    @property
    def alarm_enabled(self):
        return self._alarm_enabled()

    @alarm_enabled.setter
    def alarm_enabled(self, val: bool):
        self._alarm_enabled = val

    def check_alarm_elapsed(self):
        return datetime.now.time > self._alarm_time

    @property
    def alarm(self):
        return self._nominal_alarm_time

    @alarm.setter
    def alarm(self, val):
        self._nominal_alarm_time = val
        self.calculate_alarm(val)

    @property
    def sound(self):
        return self._sound

    @sound.setter
    def sound(self, val: bool):
        self._sound = val

    def cancel(self):
        self._sounding = False
        if self._old_alarm_time:
            self.calculate_alarm(self._old_alarm_time)
            self._old_alarm_time = None

    def snooze(self, duration: timedelta:
        if not self._sounding:
            raise AlarmError("Not sounding")

        self._old_alarm_time = self._alarm_time
        self.calculate_alarm((datetime.now + duration).time)

