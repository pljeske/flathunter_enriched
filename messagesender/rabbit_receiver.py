import json
import logging
import socket
import time

import pika
import requests
import yaml
from pika.adapters.blocking_connection import BlockingChannel

# logging.basicConfig(level=logging.NOTSET)
logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s')
log = logging.getLogger('rabbit_receiver')
log.setLevel(logging.DEBUG)


def callback(ch: BlockingChannel, method, properties, body):
    log.debug("Received message: %s", body)
    try:
        message = json.loads(body)
        log.debug("Received message: %s", message)
        # print(f"Got message: {message}")
    except json.decoder.JSONDecodeError:
        log.error("Invalid JSON message received: %s", body)
        log.error("Rejecting message...")
        ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        time.sleep(1.5)
        return

    params = message['params']
    url = message['url']

    if 'sendMessage' in url and 'text' in params and params['text'] == '':
        log.error("Can't send empty message Rejecting message...")
        ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        time.sleep(1.5)
        return

    log.debug("Sending received message: %s", message)
    resp = requests.post(url, params=params)
    log.debug("Got response (%i): %s", resp.status_code, resp.content)

    if resp.status_code == 429:
        try:
            json_resp = json.loads(resp.content)
        except json.decoder.JSONDecodeError as e:
            log.error("Invalid JSON response received: %s", resp.content)
            json_resp = resp.json()
        log.warning("Got 429 response: %s", json_resp)
        ch.basic_nack(delivery_tag=method.delivery_tag)
        try:
            retry_after = json_resp['parameters']['retry_after']
        except Exception as e:
            log.error(str(e))
            retry_after = 60
        log.warning("Retrying in %i seconds", retry_after)
        time.sleep(retry_after)
    elif resp.status_code == 400:
        log.error("Got 400 response: %s", resp.content)
        log.error("Dismissing message...")
        ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        time.sleep(1.5)
    elif resp.status_code != 200:
        log.warning("Got non-200 response: %i. Sleeping for 10 seconds", resp.status_code)
        ch.basic_nack(delivery_tag=method.delivery_tag)
        time.sleep(10)
    else:
        ch.basic_ack(delivery_tag=method.delivery_tag)
        log.debug("Message sent. Sleeping for 1 second.")
        time.sleep(1.5)


def wait_for_rabbitmq(host: str, port: int, timeout=3):
    is_reachable = False
    while not is_reachable:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((host, port))
            log.info("Connected to RabbitMQ")
            is_reachable = True
        except socket.error as e:
            log.debug("RabbitMQ not reachable: %s", e)
            log.info("Waiting for RabbitMQ to come up...")
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
    log.debug("Connecting to RabbitMQ on %s", host)
    wait_for_rabbitmq(host, 5672)
    params = pika.URLParameters(url + "?heartbeat=180")
    log.debug("Connecting to RabbitMQ on url %s", url)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue='telegram')
    channel.basic_consume(queue='telegram', auto_ack=False, on_message_callback=callback)
    try:
        log.debug("Waiting for messages...")
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    except Exception as e:
        print(e)
        channel.stop_consuming()
    connection.close()

