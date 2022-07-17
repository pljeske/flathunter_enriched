import json
import logging
import socket
import time

import pika
import requests
import yaml

log = logging.getLogger('rabbit_receiver')


def callback(ch, method, properties, body):
    log.debug("Received message: %s", body)
    print("Got message: %s", body)
    try:
        message = json.loads(body)
    except json.decoder.JSONDecodeError:
        log.debug("Invalid JSON message received: %s", body)
        print("Invalid JSON message received: %s" % body)
        return
    params = message['params']
    url = message['url']

    print("Sending received message: %s", message)
    log.debug("Sending received message: %s", message)
    resp = requests.post(url, params=params)
    log.debug("Got response (%i): %s", resp.status_code, resp.content)
    log.debug("Message sent. Sleeping for 1 second.")
    print("Got response (%i): %s", resp.status_code, resp.content)
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
        # user = 'rabbitmq'
        # password = 'rabbitmq'
    else:
        url = config['rabbitmq']['url']
        host = config['rabbitmq']['host']
        # user = config['rabbitmq']['user']
        # password = config['rabbitmq']['password']
    print(f"Connecting to RabbitMQ on {host}")
    log.debug("Connecting to RabbitMQ on %s", host)
    wait_for_rabbitmq(host, 5672)
    params = pika.URLParameters(url)
    print(f"Connecting to RabbitMQ on url {url}")
    log.debug("Connecting to RabbitMQ on url %s", url)
    connection = pika.BlockingConnection(params)
    # credentials = pika.PlainCredentials(username=user, password=password)
    # pika_params = pika.ConnectionParameters(host=host, port=5672, credentials=credentials)
    # connection = pika.BlockingConnection(pika_params)
    channel = connection.channel()
    channel.queue_declare(queue='telegram')
    channel.basic_consume(queue='telegram', auto_ack=True, on_message_callback=callback)
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

