"""Providing heartbeat messages"""
import logging
from flathunter.config import Config
from flathunter.sender_mattermost import SenderMattermost
from flathunter.sender_telegram import SenderTelegram

def interval2counter(interval):
    """Transform the string interval to sleeper counter frequencies"""
    if interval is None:
        return None
    if interval.lower() == 'hour':
        return 6
    if interval.lower() == 'day':
        return 144
    if interval.lower() == 'week':
        return 1008
    raise Exception("No valid heartbeat instruction received - no heartbeat messages will be sent.")

class Heartbeat:
    """heartbeat class - Will inform the user on regular intervals whether the bot is still alive"""
    __log__ = logging.getLogger('flathunt')

    def __init__(self, config, interval):
        self.config = config
        if not isinstance(self.config, Config):
            raise Exception("Invalid config for hunter - should be a 'Config' object")
        self.notifiers = self.config.get('notifiers', [])
        if 'mattermost' in self.notifiers:
            self.notifier = SenderMattermost(config)
        elif 'telegram' in self.notifiers:
            self.notifier = SenderTelegram(config)
        else:
            self.notifier = None
        self.interval = interval2counter(interval)

    def send_heartbeat(self, counter):
        """Send a new heartbeat message"""
        # its time for a new heartbeat message and reset counter
        if self.notifier is not None and self.interval is not None:
            if counter % self.interval == 0:
                self.notifier.send_msg(
                    'Beep Boop. This is a heartbeat message. '
                    'Your bot is searching actively for flats.'
                )
                counter = 0
        return counter
