"""Wrap configuration options as an object"""
import os
import logging
import yaml

from flathunter.captcha.imagetyperz_solver import ImageTyperzSolver
from flathunter.captcha.twocaptcha_solver import TwoCaptchaSolver
from flathunter.captcha.captcha_solver import CaptchaSolver
from flathunter.crawl_ebaykleinanzeigen import CrawlEbayKleinanzeigen
from flathunter.crawl_immobilienscout import CrawlImmobilienscout
from flathunter.crawl_wggesucht import CrawlWgGesucht
from flathunter.crawl_immowelt import CrawlImmowelt
from flathunter.crawler_subito import CrawlSubito
from flathunter.crawl_immobiliare import CrawlImmobiliare
from flathunter.crawl_idealista import CrawlIdealista
from flathunter.filter import Filter

class Config:
    """Class to represent flathunter configuration"""

    __log__ = logging.getLogger('flathunt')

    def __init__(self, filename=None, string=None):
        if string is not None:
            self.config = yaml.safe_load(string)
        else:
            if filename is None:
                filename = os.path.dirname(os.path.abspath(__file__)) + "/../config.yaml"
            self.__log__.info("Using config %s", filename)
            with open(filename, encoding="utf-8") as file:
                self.config = yaml.safe_load(file)
        self.__searchers__ = [CrawlImmobilienscout(self),
                              CrawlWgGesucht(self),
                              CrawlEbayKleinanzeigen(self),
                              CrawlImmowelt(self),
                              CrawlSubito(self),
                              CrawlImmobiliare(self),
                              CrawlIdealista(self)]

    def __iter__(self):
        """Emulate dictionary"""
        return self.config.__iter__()

    def __getitem__(self, value):
        """Emulate dictionary"""
        return self.config[value]

    def get(self, key, value=None):
        """Emulate dictionary"""
        return self.config.get(key, value)

    def database_location(self):
        """Return the location of the database folder"""
        if "database_location" in self.config:
            return self.config["database_location"]
        return os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + "/..")

    def set_searchers(self, searchers):
        """Update the active search plugins"""
        self.__searchers__ = searchers

    def searchers(self):
        """Get the list of search plugins"""
        return self.__searchers__

    def get_filter(self):
        """Read the configured filter"""
        builder = Filter.builder()
        builder.read_config(self.config)
        return builder.build()

    def captcha_enabled(self):
        """Check if captcha is configured"""
        return "captcha" in self.config

    def get_captcha_solver(self) -> CaptchaSolver:
        """Get configured captcha solver"""
        captcha_config = self.config.get("captcha", {})

        if captcha_config.get("imagetypers") is not None:
            self.__log__.warning(
                'Captcha configuration for "imagetypers" has been renamed to "imagetyperz". '
                'We found an outdated entry, which has to be renamed accordingly, in order '
                'to be detected again.'
            )

        imagetyperz_token = captcha_config.get("imagetyperz", {}).get("token", "")
        twocaptcha_api_key = captcha_config.get("2captcha", {}).get("api_key", "")

        if imagetyperz_token:
            return ImageTyperzSolver(imagetyperz_token)
        if twocaptcha_api_key:
            return TwoCaptchaSolver(twocaptcha_api_key)

        raise Exception("No captcha solver configured properly.")

    def get_rabbitmq_host(self) -> str:
        """Get the url of the rabbitmq server"""
        if "rabbitmq" in self.config and "host" in self.config["rabbitmq"]:
            return self.config["rabbitmq"]["host"]
        return "localhost"

    def get_rabbitmq_user(self) -> str:
        if "rabbitmq" in self.config and "user" in self.config["rabbitmq"]:
            return self.config["rabbitmq"]["user"]
        return "rabbitmq"

    def get_rabbitmq_password(self) -> str:
        if "rabbitmq" in self.config and "password" in self.config["rabbitmq"]:
            return self.config["rabbitmq"]["password"]
        return "rabbitmq"

    def get_rabbitmq_port(self) -> int:
        if "rabbitmq" in self.config and "port" in self.config["rabbitmq"]:
            return self.config["rabbitmq"]["port"]
        return 5672

    def get_rabbitmq_url(self) -> str:
        if "rabbitmq" in self.config and "url" in self.config["rabbitmq"]:
            return self.config["rabbitmq"]["url"]
        return "amqp://rabbitmq:rabbitmq@localhost:5672/"


    def use_proxy(self):
        """Check if proxy is configured"""
        return ("use_proxy_list" in self.config and self.config["use_proxy_list"])
