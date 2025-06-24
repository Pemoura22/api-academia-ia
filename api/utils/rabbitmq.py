# api/utils/rabbitmq.py

import pika
import json
import os
from datetime import datetime, timezone  # Adicionado 'timezone' aqui

# Configurações do RabbitMQ
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')


def publish_message(queue_name, message):
    """
    Publica uma mensagem em uma fila específica do RabbitMQ.
    """
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

        channel.queue_declare(queue=queue_name, durable=True)

        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,
            )
        )
        print(f" [x] Mensagem enviada para a fila '{queue_name}': {message}")
        connection.close()
        return True
    except pika.exceptions.AMQPConnectionError as e:
        print(f" [ERROR] Não foi possível conectar ao RabbitMQ: {e}")
        return False
    except Exception as e:
        print(f" [ERROR] Erro ao publicar mensagem no RabbitMQ: {e}")
        return False
