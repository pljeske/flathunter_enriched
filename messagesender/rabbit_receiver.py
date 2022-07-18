import json
import logging
import socket
import time

import pika
import requests
import yaml
from pika.adapters.blocking_connection import BlockingChannel

log = logging.getLogger('rabbit_receiver')


def callback(ch: BlockingChannel, method, properties, body):
    log.debug("Received message: %s", body)
    try:
        message = json.loads(body)
        print(f"Got message: {message}")
    except json.decoder.JSONDecodeError:
        log.debug("Invalid JSON message received: %s", body)
        print(f"Invalid JSON message received: {body}")
        return
    params = message['params']
    url = message['url']

    print(f"Sending received message: {message}")
    log.debug("Sending received message: %s", message)
    resp = requests.post(url, params=params)
    log.debug("Got response (%i): %s", resp.status_code, resp.content)

    if resp.status_code == 429:
        # json_resp = json.loads(resp.json())
        json_resp = resp.json()
        ch.basic_nack(delivery_tag=method.delivery_tag)
        retry_after = json_resp.get("parameters", {"retry-after": 60}).get("retry-after") + 2
        log.warning("Got 429 response. Retrying in %i seconds", retry_after)
        print(f"Got 429 response. Retrying in {retry_after} seconds")
        time.sleep(retry_after)
    elif resp.status_code != 200:
        log.warning("Got non-200 response: %i", resp.status_code)
        print(f"Got non-200 response: {resp.status_code}. Sleeping for 10 seconds")
        ch.basic_nack(delivery_tag=method.delivery_tag)
        time.sleep(10)
    else:
        ch.basic_ack(delivery_tag=method.delivery_tag)
        log.debug("Message sent. Sleeping for 1 second.")
        print(f"Got response ({resp.status_code}): {resp.content}")
        print("Message sent. Sleeping for 1 second.")
        time.sleep(1.5)


def wait_for_rabbitmq(host: str, port: int, timeout=3):
    is_reachable = False
    while not is_reachable:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((host, port))
            print("Connected to RabbitMQ")
            is_reachable = True
        except socket.error as e:
            log.debug("RabbitMQ not reachable: %s", e)
            log.info("Waiting for RabbitMQ to come up...")
            print("RabbitMQ not (yet) reachable: ", str(e))
            time.sleep(timeout)


if __name__ == '__main__':
    config = yaml.safe_load(open('config.yaml', encoding="utf-8"))
    log.setLevel(logging.DEBUG)
    if config is None or config.get('rabbitmq') is None:
        url = "amqp://rabbitmq:rabbitmq@rabbitmq:5672/"
        host = 'localhost'
    else:
        url = config['rabbitmq']['url']
        host = config['rabbitmq']['host']
    print(f"Connecting to RabbitMQ on {host}")
    log.debug("Connecting to RabbitMQ on %s", host)
    wait_for_rabbitmq(host, 5672)
    params = pika.URLParameters(url)
    print(f"Connecting to RabbitMQ on url {url}")
    log.debug("Connecting to RabbitMQ on url %s", url)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue='telegram')
    channel.basic_consume(queue='telegram', auto_ack=False, on_message_callback=callback)
    try:
        print("Waiting for messages...")
        log.debug("Waiting for messages...")
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    except Exception as e:
        print(e)
        channel.stop_consuming()
    connection.close()

