#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Flathunter - search for flats by crawling property portals, and receive telegram
   messages about them. This is the main command-line executable, for running on the
   console. To run as a webservice, look at main.py"""

import argparse
import os
import logging
import time
from pprint import pformat

from flathunter.idmaintainer import IdMaintainer
from flathunter.hunter import Hunter
from flathunter.config import Config
from flathunter.heartbeat import Heartbeat

__author__ = "Jan Harrie"
__version__ = "1.0"
__maintainer__ = "Nody"
__email__ = "harrymcfly@protonmail.com"
__status__ = "Production"

# init logging
if os.name == 'posix':
    # coloring on linux
    CYELLOW = '\033[93m'
    CBLUE = '\033[94m'
    COFF = '\033[0m'
    LOG_FORMAT = '[' + CBLUE + '%(asctime)s' + COFF + '|' + CBLUE + '%(filename)-18s' + COFF + \
                 '|' + CYELLOW + '%(levelname)-8s' + COFF + ']: %(message)s'
else:
    # else without color
    LOG_FORMAT = '[%(asctime)s|%(filename)-18s|%(levelname)-8s]: %(message)s'
logging.basicConfig(
    format=LOG_FORMAT,
    datefmt='%Y/%m/%d %H:%M:%S',
    level=logging.INFO)
__log__ = logging.getLogger('flathunt')


def launch_flat_hunt(config, heartbeat=None):
    """Starts the crawler / notification loop"""
    id_watch = IdMaintainer(f'{config.database_location()}/processed_ids.db')

    hunter = Hunter(config, id_watch)
    hunter.hunt_flats()
    counter = 0

    while config.get('loop', {}).get('active', False):
        counter += 1
        counter = heartbeat.send_heartbeat(counter)
        time.sleep(config.get('loop', {}).get('sleeping_time', 60 * 10))
        hunter.hunt_flats()


def main():
    """Processes command-line arguments, loads the config, launches the flathunter"""
    parser = argparse.ArgumentParser(
        description=("Searches for flats on Immobilienscout24.de and wg-gesucht.de"
                     " and sends results to Telegram User"),
        epilog="Designed by Nody"
    )
    default_config_path = f"{os.path.dirname(os.path.abspath(__file__))}/config.yaml"
    parser.add_argument('--config', '-c',
                        type=argparse.FileType('r', encoding='UTF-8'),
                        default=default_config_path,
                        help=f'Config file to use. If not set, try to use "{default_config_path}"'
                        )
    parser.add_argument('--heartbeat', '-hb',
                        action='store',
                        default=None,
                        help=('Set the interval time to receive heartbeat messages to check'
                              'that the bot is alive. Accepted strings are "hour", "day", "week".'
                              'Defaults to None.')
                        )
    args = parser.parse_args()

    # load config
    config_handle = args.config
    config = Config(config_handle.name)

    # check config
    notifiers = config.get('notifiers', [])
    if 'mattermost' in notifiers \
            and not config.get('mattermost', {}).get('webhook_url'):
        __log__.error("No mattermost webhook configured. Starting like this would be pointless...")
        return
    if 'telegram' in notifiers:
        if not config.get('telegram', {}).get('bot_token'):
            __log__.error(
                "No telegram bot token configured. Starting like this would be pointless..."
            )
            return
        if not config.get('telegram', {}).get('receiver_ids'):
            __log__.warning("No telegram receivers configured - nobody will get notifications.")
    if not config.get('urls'):
        __log__.error("No urls configured. Starting like this would be meaningless...")
        return

    # get heartbeat instructions
    heartbeat_interval = args.heartbeat
    heartbeat = Heartbeat(config, heartbeat_interval)

    # adjust log level, if required
    if config.get('verbose'):
        __log__.setLevel(logging.DEBUG)
        __log__.debug("Settings from config: %s", pformat(config))

    # start hunting for flats
    launch_flat_hunt(config, heartbeat)


if __name__ == "__main__":
    main()
