# consumer.py

import pika
import json
import os
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone

# Importações dos modelos do seu projeto
from api.models.aluno import Aluno
from api.models.checkin import Checkin
from api.models.plano import Plano
from api.config import Config
from churn_model import ChurnPredictor  # <<< IMPORTAÇÃO CHAVE AQUI!

# Configurações do RabbitMQ
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')
RABBITMQ_QUEUE = "checkin_queue"

# Configuração do Banco de Dados para o Consumidor
DATABASE_URL = Config.SQLALCHEMY_DATABASE_URI
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# Instância global do preditor de churn para o consumidor
# O modelo será carregado/treinado uma vez quando o consumidor iniciar.
churn_predictor_consumer = ChurnPredictor()


def process_checkin_message(ch, method, properties, body):
    session = Session()
    try:
        message_data = json.loads(body)
        message_type = message_data.get('type')

        print(f" [x] Mensagem recebida (Tipo: {message_type}): {message_data}")

        if message_type == 'new_checkin_event':
            checkin_id = message_data.get('checkin_id')
            id_aluno = message_data.get('id_aluno')
            print(
                f" [INFO] Processando check-in individual ID: {checkin_id} para Aluno ID: {id_aluno}")
            time.sleep(1)
            print(
                f" [INFO] Check-in individual ID {checkin_id} processado com sucesso.")

        elif message_type == 'bulk_checkin_event':
            checkin_ids = message_data.get('checkin_ids', [])
            print(
                f" [INFO] Processando check-ins em massa. IDs: {checkin_ids}")
            for single_id in checkin_ids:
                print(
                    f"   [SUB-PROCESS] Processando check-in em massa ID: {single_id}")
                time.sleep(0.5)
            print(
                f" [INFO] Todos os {len(checkin_ids)} check-ins em massa foram processados.")

        elif message_type == 'generate_daily_report_event':
            report_date_str = message_data.get(
                'report_date', datetime.now(timezone.utc).date().isoformat())
            report_date = datetime.fromisoformat(report_date_str).date()

            print(
                f" [INFO] Gerando relatório diário de frequência para a data: {report_date}")

            start_of_day = datetime(
                report_date.year, report_date.month, report_date.day, tzinfo=timezone.utc)
            end_of_day = start_of_day + timedelta(days=1)

            daily_checkins = session.query(Checkin).filter(
                Checkin.timestamp_checkin >= start_of_day,
                Checkin.timestamp_checkin < end_of_day
            ).all()

            total_daily_checkins = len(daily_checkins)
            unique_alunos_ids = set()
            for checkin in daily_checkins:
                unique_alunos_ids.add(checkin.id_aluno)
            total_unique_alunos = len(unique_alunos_ids)

            print(
                f"   [RELATÓRIO] Relatório de Frequência para {report_date.isoformat()}:")
            print(f"   Total de Check-ins no dia: {total_daily_checkins}")
            print(f"   Total de Alunos Únicos: {total_unique_alunos}")

            time.sleep(3)
            print(
                f" [INFO] Relatório para {report_date.isoformat()} gerado com sucesso.")

        # --- LÓGICA CORRIGIDA: Acionar Retreinamento do Modelo de Churn ---
        elif message_type == 'retrain_model_event':  # <<< ESTA LINHA DEVE SER ATINGIDA AGORA!
            print(" [INFO] Acionando retreinamento do modelo de churn...")
            # Chama o método de retreinamento do modelo global do consumidor
            churn_predictor_consumer.retrain_and_save_model()
            print(
                " [INFO] Retreinamento do modelo de churn finalizado via consumidor.")
        # --- FIM DA LÓGICA CORRIGIDA ---

        else:
            print(
                f" [WARNING] Tipo de mensagem desconhecido: {message_type}. Mensagem: {message_data}")

        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(
            f" [x] Mensagem confirmada (ACK) para delivery_tag: {method.delivery_tag}")

    except json.JSONDecodeError:
        print(f" [ERROR] Falha ao decodificar JSON da mensagem: {body}")
        session.rollback()
        ch.basic_nack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f" [ERROR] Erro ao processar mensagem: {e}. Mensagem: {body}")
        session.rollback()
        ch.basic_nack(delivery_tag=method.delivery_tag)
    finally:
        session.close()


def start_consuming():
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials,
            heartbeat=600
        )
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

        channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
        channel.basic_qos(prefetch_count=1)

        print(
            f' [*] Consumidor aguardando mensagens na fila "{RABBITMQ_QUEUE}". Para sair, pressione CTRL+C.')

        channel.basic_consume(queue=RABBITMQ_QUEUE,
                              on_message_callback=process_checkin_message)
        channel.start_consuming()

    except pika.exceptions.AMQPConnectionError as e:
        print(
            f" [ERROR] Não foi possível conectar ao RabbitMQ: {e}. Verifique se o servidor RabbitMQ está rodando e acessível.")
        print(" [DICA] Tente acessar http://localhost:15672 no seu navegador para verificar o status do RabbitMQ.")
    except KeyboardInterrupt:
        print(" [*] Consumidor interrompido pelo usuário.")
    except Exception as e:
        print(f" [ERROR] Ocorreu um erro inesperado no consumidor: {e}")
    finally:
        if 'connection' in locals() and connection.is_open:
            connection.close()
            print(" [*] Conexão com RabbitMQ fechada.")


if __name__ == '__main__':
    start_consuming()
