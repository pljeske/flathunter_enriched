"""Functions and classes related to sending Telegram messages"""
import socket
import urllib.request
import urllib.parse
import urllib.error
import logging
import time

import requests
import json

from flathunter.abstract_processor import Processor
import pika


class SenderTelegram(Processor):
    """Expose processor that sends Telegram messages"""
    __log__ = logging.getLogger('flathunt')

    def __init__(self, config, receivers=None):
        self.config = config
        self.bot_token = self.config.get('telegram', {}).get('bot_token', '')
        self.send_msg_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.send_image_url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        self.send_media_group_url = f"https://api.telegram.org/bot{self.bot_token}/sendMediaGroup"
        if receivers is None:
            self.receiver_ids = self.config.get('telegram', {}).get('receiver_ids', [])
        else:
            self.receiver_ids = receivers
        try:
            self.wait_for_connection(self.config.get_rabbitmq_host(), self.config.get_rabbitmq_port())
            connected = False
            while not connected:
                try:
                    credentials = pika.PlainCredentials(self.config.get_rabbitmq_user(),
                                                        self.config.get_rabbitmq_password())
                    pika_params = pika.ConnectionParameters(host=self.config.get_rabbitmq_host(),
                                                            port=self.config.get_rabbitmq_port(),
                                                            credentials=credentials)
                    connection = pika.BlockingConnection(pika_params)
                    self.channel = connection.channel()
                    connected = True
                except Exception as e:
                    self.__log__.error("Error connecting to RabbitMQ: %s", e)
                    time.sleep(1)

            self.channel.queue_declare(queue='telegram')
        except Exception as e:
            self.__log__.error("Could not connect to RabbitMQ", e)
            self.channel = None

    def process_expose(self, expose):
        """Send a message to a user describing the expose"""
        self.__log__.debug(f"Processing expose: {expose}")
        message = self.config.get('message', "").format(
            title=expose['title'],
            rooms=expose['rooms'],
            size=expose['size'],
            price=expose['price'],
            rent_warm=expose['rent_warm'],
            url=expose['url'],
            address=expose['address'],
            durations="" if 'durations' not in expose else expose['durations']).strip()
        self.send_msg(message)

        image_urls = expose['images']
        if image_urls is not None and len(image_urls) > 0:
            self.send_pictures(image_urls)
        else:
            self.__log__.debug("No images to send")

        if expose['description'] is not None and not expose['description'].isspace():
            self.send_msg(expose['description'], new_listing=False)

        return expose

    def send_msg(self, message: str, new_listing=True):
        """Send messages to each of the receivers in receiver_ids"""
        if self.receiver_ids is None:
            return
        for chat_id in self.receiver_ids:
            if new_listing:
                self.send(self.send_msg_url, {'chat_id': chat_id, 'text': '------------NEW LISTING------------'})

            max_length = 4095
            if len(message) > max_length:
                self.__log__.debug("Message is too long, sending in multiple messages")
                messages = [message[i:i+max_length] for i in range(0, len(message), max_length)]
                for msg in messages:
                    self.__log__.debug(('text', msg))
                    self.send(self.send_msg_url, {'chat_id': chat_id, 'text': msg})
            else:
                self.__log__.debug(('token:', self.bot_token))
                self.__log__.debug(('chatid:', chat_id))
                self.__log__.debug(('text', message))
                self.send(self.send_msg_url, {'chat_id': chat_id, 'text': message})

    def send_pictures(self, image_urls):
        if self.receiver_ids is None:
            return
        for chat_id in self.receiver_ids:
            image_urls = [image_url.split("/ORIG")[0] for image_url in image_urls]
            if len(image_urls) == 1:
                self.__log__.debug("Sending one picture")
                self.__log__.debug("Image URL: %s", image_urls[0])
                self.send_one_picture(chat_id, image_urls[0])
            elif 1 < len(image_urls) < 10:
                self.__log__.debug("Sending %i pictures", len(image_urls))
                self.__log__.debug("Pictures: %s", image_urls)
                self.send_multiple_pictures(chat_id, image_urls)
            else:
                number_of_messages = len(image_urls) // 9 + 1
                for i in range(number_of_messages):
                    images_to_send = image_urls[i * 9:i * 9 + 9]
                    if len(images_to_send) > 1:
                        self.__log__.debug("Sending %i images", len(images_to_send))
                        self.__log__.debug("Images: %s", images_to_send)
                        self.send_multiple_pictures(chat_id, images_to_send)
                    else:
                        self.__log__.debug("Sending image number %i", i)
                        self.__log__.debug("Image: %s", images_to_send[0])
                        self.send_one_picture(chat_id, images_to_send[0])

    def send_one_picture(self, chat_id, image_url):
        self.__log__.debug("Sending image %s", image_url)
        self.send(self.send_image_url, {'chat_id': chat_id, 'photo': image_url})

    def send_multiple_pictures(self, chat_id, image_urls):
        params = {
            "chat_id": chat_id,
            "media": []
        }

        for picture in image_urls:
            params["media"].append({"type": "photo", "media": picture})

        params['media'] = json.dumps(params['media'])

        self.send(self.send_media_group_url, params)

    def send(self, url, params):
        if self.channel is not None:
            rabbit_msg = {'url': url, 'params': params}
            self.channel.basic_publish(exchange='', routing_key='telegram', body=json.dumps(rabbit_msg))
        else:
            requests.post(url, params=params)

    def wait_for_connection(self, host: str, port=5672, timeout=3):
        is_reachable = False
        while not is_reachable:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.connect((host, port))
                print("Connected to RabbitMQ")
                is_reachable = True
            except socket.error as e:
                self.__log__.debug("Waiting for RabbitMQ to be reachable: %s", e)
                time.sleep(timeout)
