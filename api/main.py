# api/main.py

from flask import Flask, jsonify, request
# Novas importações para Swagger
from flask_restx import Api, Namespace, Resource, fields
from api.config import Config
from api.database import db, init_db
from api.models.plano import Plano
from api.models.aluno import Aluno
from api.models.checkin import Checkin
from datetime import datetime, timedelta, timezone
from api.utils.rabbitmq import publish_message
from churn_model import ChurnPredictor

# Instância global do preditor de churn. O modelo será carregado/treinado uma vez ao iniciar a aplicação.
churn_predictor = ChurnPredictor()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    init_db(app)

    # Configuração do Flask-RESTX para Swagger UI
    api = Api(
        app,
        version='1.0',
        title='API de Gerenciamento de Academia com IA',
        description='API para gerenciar planos, alunos, check-ins e prever risco de churn utilizando Machine Learning.',
        doc='/docs/'  # A URL para acessar a documentação Swagger
    )

    # Namespace para os recursos da API
    ns_planos = api.namespace(
        'planos', description='Operações relacionadas a planos de academia')
    ns_alunos = api.namespace(
        'alunos', description='Operações relacionadas a alunos')
    ns_checkins = api.namespace(
        'checkins', description='Operações relacionadas a check-ins')
    ns_model = api.namespace(
        'model', description='Operações relacionadas ao modelo de Machine Learning')

    # --- Modelos de dados para Swagger UI ---
    plano_model = api.model('Plano', {
        'id': fields.Integer(readOnly=True, description='Identificador único do plano'),
        'nome_plano': fields.String(required=True, description='Nome do plano (ex: Mensal, Trimestral)'),
        'preco': fields.Float(required=True, description='Preço do plano'),
        'descricao': fields.String(description='Descrição detalhada do plano'),
    })

    aluno_model = api.model('Aluno', {
        'id': fields.Integer(readOnly=True, description='Identificador único do aluno'),
        'nome': fields.String(required=True, description='Nome completo do aluno'),
        'email': fields.String(required=True, description='Email do aluno (deve ser único)'),
        'data_nascimento': fields.Date(description='Data de nascimento do aluno (AAAA-MM-DD)'),
        'data_matricula': fields.DateTime(readOnly=True, description='Data e hora da matrícula (ISO 8601)'),
        'id_plano': fields.Integer(required=True, description='ID do plano associado ao aluno'),
        'status': fields.String(description='Status do aluno (ex: Ativo, Inativo, Suspenso)', enum=['Ativo', 'Inativo', 'Suspenso']),
    })

    checkin_model = api.model('Checkin', {
        'id': fields.Integer(readOnly=True, description='Identificador único do check-in'),
        'id_aluno': fields.Integer(required=True, description='ID do aluno que realizou o check-in'),
        'timestamp_checkin': fields.DateTime(description='Data e hora do check-in (ISO 8601)', default=lambda: datetime.now(timezone.utc).isoformat()),
        'duracao_minutos': fields.Integer(description='Duração da visita em minutos'),
    })

    risco_churn_metrics_model = api.model('RiscoChurnMetrics', {
        'frequencia_semanal': fields.Float(description='Frequência média de check-ins por semana'),
        'dias_desde_ultimo_checkin': fields.Integer(description='Número de dias desde o último check-in'),
        'duracao_media_visitas_minutos': fields.Float(description='Duração média das visitas em minutos'),
        'tipo_plano_encoded': fields.Integer(description='Tipo de plano codificado (1=Mensal, 2=Trimestral, 3=Anual)'),
        'total_checkins_registrados': fields.Integer(description='Total de check-ins registrados para o aluno'),
    })

    risco_churn_response_model = api.model('RiscoChurnResponse', {
        'aluno_id': fields.Integer(description='ID do aluno'),
        'nome_aluno': fields.String(description='Nome do aluno'),
        'risco_churn_classificacao': fields.String(description='Classificação do risco de churn (Ex: Baixo, Médio, Alto, Muito Alto)'),
        'probabilidade_churn': fields.Float(description='Probabilidade de churn prevista pelo modelo (0.00 - 1.00)'),
        'motivos': fields.List(fields.String, description='Lista de motivos ou fatores que contribuem para o risco'),
        'metricas_calculadas': fields.Nested(risco_churn_metrics_model, description='Métricas calculadas e usadas para a previsão'),
    })

    frequencia_historico_item_model = api.model('FrequenciaHistoricoItem', {
        'id_checkin': fields.Integer(description='ID do check-in'),
        'timestamp': fields.String(description='Timestamp do check-in (ISO 8601)'),
        'duracao_minutos': fields.Integer(description='Duração da visita em minutos'),
    })

    frequencia_response_model = api.model('FrequenciaResponse', {
        'aluno_id': fields.Integer(description='ID do aluno'),
        'nome_aluno': fields.String(description='Nome do aluno'),
        'total_checkins': fields.Integer(description='Número total de check-ins do aluno'),
        'historico': fields.List(fields.Nested(frequencia_historico_item_model), description='Histórico detalhado de check-ins'),
    })

    # --- Rota Home (fora do namespace) ---
    @app.route('/')
    class Home(Resource):
        def get(self):
            """
            Retorna uma mensagem de boas-vindas à API.
            """
            return jsonify({"message": "Bem-vindo à API de Gerenciamento de Academia com IA!"})

    # --- Rotas para Planos ---

    @ns_planos.route('/')
    class PlanoList(Resource):
        @ns_planos.doc('list_planos')
        @ns_planos.marshal_list_with(plano_model)
        def get(self):
            """Lista todos os planos de academia."""
            planos = Plano.query.all()
            return planos

    # --- Rotas para Alunos ---
    @ns_alunos.route('/')
    class AlunoList(Resource):
        @ns_alunos.doc('list_alunos')
        @ns_alunos.marshal_list_with(aluno_model)
        def get(self):
            """Lista todos os alunos cadastrados."""
            alunos = Aluno.query.all()
            return alunos

        @ns_alunos.doc('create_aluno')
        @ns_alunos.expect(aluno_model)
        @ns_alunos.marshal_with(aluno_model, code=201)
        @ns_alunos.response(400, 'Dados inválidos')
        @ns_alunos.response(404, 'Plano não encontrado')
        def post(self):
            """Cria um novo aluno."""
            data = request.get_json()
            if not data:
                api.abort(400, "Dados inválidos ou formato JSON incorreto.")

            if 'nome' not in data or 'email' not in data:
                api.abort(400, "Nome e email são campos obrigatórios.")

            if 'id_plano' not in data or data['id_plano'] is None:
                api.abort(400, "id_plano é obrigatório.")

            data_nascimento = data.get('data_nascimento')
            if data_nascimento:
                try:
                    data_nascimento = datetime.strptime(
                        data_nascimento, '%Y-%m-%d').date()
                except ValueError:
                    api.abort(
                        400, "Formato de data de nascimento inválido. Use AAAA-MM-DD.")

            id_plano = data.get('id_plano')
            plano_existe = Plano.query.get(id_plano)
            if not plano_existe:
                api.abort(404, f"Plano com ID {id_plano} não encontrado.")

            novo_aluno = Aluno(
                nome=data['nome'],
                email=data['email'],
                data_nascimento=data_nascimento,
                id_plano=id_plano,
            )

            db.session.add(novo_aluno)
            db.session.commit()
            return novo_aluno, 201

    @ns_alunos.route('/<int:id>')
    @ns_alunos.response(404, 'Aluno não encontrado')
    class AlunoResource(Resource):
        @ns_alunos.doc('get_aluno')
        @ns_alunos.marshal_with(aluno_model)
        def get(self, id):
            """Retorna um aluno pelo seu ID."""
            aluno = Aluno.query.get_or_404(id)
            return aluno

        @ns_alunos.doc('update_aluno')
        @ns_alunos.expect(aluno_model)
        @ns_alunos.marshal_with(aluno_model)
        def put(self, id):
            """Atualiza um aluno existente."""
            aluno = Aluno.query.get_or_404(id)
            data = request.get_json()
            if not data:
                api.abort(400, "Dados inválidos.")

            if 'nome' in data:
                aluno.nome = data['nome']
            if 'email' in data:
                aluno.email = data['email']

            if 'data_nascimento' in data:
                data_nascimento = data.get('data_nascimento')
                if data_nascimento:
                    try:
                        aluno.data_nascimento = datetime.strptime(
                            data_nascimento, '%Y-%m-%d').date()
                    except ValueError:
                        api.abort(
                            400, "Formato de data de nascimento inválido. Use AAAA-MM-DD.")
                else:
                    aluno.data_nascimento = None

            if 'id_plano' in data:
                id_plano = data.get('id_plano')
                if id_plano:
                    plano_existe = Plano.query.get(id_plano)
                    if not plano_existe:
                        api.abort(
                            404, f"Plano com ID {id_plano} não encontrado.")
                aluno.id_plano = id_plano

            if 'data_matricula' in data:
                data_matricula = data.get('data_matricula')
                if data_matricula:
                    try:
                        aluno.data_matricula = datetime.fromisoformat(
                            data_matricula)
                    except ValueError:
                        api.abort(
                            400, "Formato de data de matrícula inválido. Use ISO 8601 (AAAA-MM-DDTHH:MM:SS).")
                else:
                    aluno.data_matricula = None

            if 'status' in data:
                aluno.status = data['status']

            db.session.commit()
            return aluno

        @ns_alunos.doc('delete_aluno')
        @ns_alunos.response(204, 'Aluno deletado com sucesso')
        def delete(self, id):
            """Deleta um aluno pelo seu ID."""
            aluno = Aluno.query.get_or_404(id)
            db.session.delete(aluno)
            db.session.commit()
            return '', 204

    @ns_alunos.route('/<int:id>/frequencia')
    @ns_alunos.response(404, 'Aluno não encontrado')
    class AlunoFrequencia(Resource):
        @ns_alunos.doc('get_aluno_frequencia')
        @ns_alunos.marshal_with(frequencia_response_model)
        def get(self, id):
            """Retorna o histórico de frequência de check-ins de um aluno."""
            aluno = Aluno.query.get_or_404(id)
            checkins_do_aluno = db.session.query(Checkin).filter_by(
                id_aluno=aluno.id).order_by(Checkin.timestamp_checkin.asc()).all()

            historico_frequencia = []
            for checkin in checkins_do_aluno:
                historico_frequencia.append({
                    "id_checkin": checkin.id,
                    "timestamp": checkin.timestamp_checkin.isoformat(),
                    "duracao_minutos": checkin.duracao_minutos
                })

            return {
                "aluno_id": aluno.id,
                "nome_aluno": aluno.nome,
                "total_checkins": len(historico_frequencia),
                "historico": historico_frequencia
            }

    @ns_alunos.route('/<int:id>/risco-churn')
    @ns_alunos.response(404, 'Aluno não encontrado')
    class AlunoRiscoChurn(Resource):
        @ns_alunos.doc('get_aluno_risco_churn')
        @ns_alunos.marshal_with(risco_churn_response_model)
        def get(self, id):
            """Retorna a probabilidade de risco de churn para um aluno, usando o modelo de ML."""
            aluno = Aluno.query.get_or_404(id)

            tipo_plano_encoded = 0
            if aluno.plano:
                if aluno.plano.nome_plano == 'Mensal':
                    tipo_plano_encoded = 1
                elif aluno.plano.nome_plano == 'Trimestral':
                    tipo_plano_encoded = 2
                elif aluno.plano.nome_plano == 'Anual':
                    tipo_plano_encoded = 3

            checkins_do_aluno = db.session.query(Checkin).filter_by(
                id_aluno=aluno.id).order_by(Checkin.timestamp_checkin.desc()).all()

            dias_desde_ultimo_checkin = None
            if checkins_do_aluno:
                ultimo_checkin_timestamp = checkins_do_aluno[0].timestamp_checkin
                if ultimo_checkin_timestamp.tzinfo is None:
                    ultimo_checkin_timestamp = ultimo_checkin_timestamp.replace(
                        tzinfo=timezone.utc)

                diferenca = datetime.now(
                    timezone.utc) - ultimo_checkin_timestamp
                dias_desde_ultimo_checkin = diferenca.days
            else:
                dias_desde_ultimo_checkin = 999

            duracao_media_visitas_minutos = 0
            total_checkins = len(checkins_do_aluno)
            if total_checkins > 0:
                total_duracao = sum(
                    [c.duracao_minutos for c in checkins_do_aluno if c.duracao_minutos is not None])
                if total_duracao > 0:
                    duracao_media_visitas_minutos = total_duracao / total_checkins

            frequencia_semanal = 0
            if checkins_do_aluno:
                primeiro_checkin_timestamp = checkins_do_aluno[-1].timestamp_checkin if checkins_do_aluno else None

                if primeiro_checkin_timestamp:
                    if primeiro_checkin_timestamp.tzinfo is None:
                        primeiro_checkin_timestamp = primeiro_checkin_timestamp.replace(
                            tzinfo=timezone.utc)

                    total_dias_ativo = (datetime.now(
                        timezone.utc) - primeiro_checkin_timestamp).days
                    if total_dias_ativo > 0:
                        frequencia_semanal = (
                            len(checkins_do_aluno) / total_dias_ativo) * 7

                checkins_ultimos_30_dias = [
                    c for c in checkins_do_aluno if c.timestamp_checkin.replace(tzinfo=timezone.utc) >= (datetime.now(timezone.utc) - timedelta(days=30))
                ]
                if len(checkins_ultimos_30_dias) > 0:
                    frequencia_semanal = len(checkins_ultimos_30_dias) / (30/7)

            aluno_metrics = {
                'frequencia_semanal': frequencia_semanal,
                'dias_desde_ultimo_checkin': dias_desde_ultimo_checkin,
                'duracao_media_visitas_minutos': round(duracao_media_visitas_minutos, 1),
                'tipo_plano_encoded': tipo_plano_encoded
            }

            churn_prob = churn_predictor.predict_churn_probability(
                aluno_metrics)

            risco_churn_classificacao = "Indeterminado"
            motivos_risco = []

            if churn_prob is not None:
                if churn_prob >= 0.7:
                    risco_churn_classificacao = "Muito Alto"
                    motivos_risco.append(
                        f"Probabilidade de Churn muito alta ({churn_prob:.2f}).")
                elif churn_prob >= 0.5:
                    risco_churn_classificacao = "Alto"
                    motivos_risco.append(
                        f"Probabilidade de Churn alta ({churn_prob:.2f}).")
                elif churn_prob >= 0.3:
                    risco_churn_classificacao = "Médio"
                    motivos_risco.append(
                        f"Probabilidade de Churn média ({churn_prob:.2f}).")
                else:
                    risco_churn_classificacao = "Baixo"
                    motivos_risco.append(
                        f"Probabilidade de Churn baixa ({churn_prob:.2f}).")

                if dias_desde_ultimo_checkin is not None and dias_desde_ultimo_checkin > 15 and risco_churn_classificacao != "Baixo":
                    motivos_risco.append(
                        f"Último check-in há {dias_desde_ultimo_checkin} dias.")
                if duracao_media_visitas_minutos < 30 and total_checkins > 5 and risco_churn_classificacao != "Baixo":
                    motivos_risco.append(
                        f"Duração média de visitas baixa ({duracao_media_visitas_minutos:.1f} min).")
                if frequencia_semanal < 1 and total_checkins > 5 and risco_churn_classificacao != "Baixo":
                    motivos_risco.append(
                        f"Frequência semanal abaixo de 1 ({frequencia_semanal:.1f}).")

            else:
                motivos_risco.append(
                    "Não foi possível gerar previsão de churn (modelo indisponível ou erro).")
                risco_churn_classificacao = "Erro na Previsão"

            if not checkins_do_aluno:
                risco_churn_classificacao = "Indeterminado"
                motivos_risco = [
                    "Sem check-ins registrados para análise de churn."]
                dias_desde_ultimo_checkin = "N/A"
                duracao_media_visitas_minutos = 0
                frequencia_semanal = 0

            return {
                "aluno_id": aluno.id,
                "nome_aluno": aluno.nome,
                "risco_churn_classificacao": risco_churn_classificacao,
                "probabilidade_churn": round(churn_prob, 2) if churn_prob is not None else "N/A",
                "motivos": list(set(motivos_risco)),
                "metricas_calculadas": {
                    "frequencia_semanal": round(frequencia_semanal, 2),
                    "dias_desde_ultimo_checkin": dias_desde_ultimo_checkin,
                    "duracao_media_visitas_minutos": round(duracao_media_visitas_minutos, 1),
                    "tipo_plano_encoded": tipo_plano_encoded,
                    "total_checkins_registrados": total_checkins
                }
            }

    # --- Rotas para Check-ins ---

    @ns_checkins.route('/')
    class CheckinList(Resource):
        @ns_checkins.doc('list_checkins')
        @ns_checkins.marshal_list_with(checkin_model)
        def get(self):
            """Lista todos os check-ins registrados."""
            checkins = Checkin.query.all()
            return checkins

        @ns_checkins.doc('create_checkin')
        @ns_checkins.expect(checkin_model)
        @ns_checkins.marshal_with(checkin_model, code=201)
        @ns_checkins.response(400, 'Dados inválidos')
        @ns_checkins.response(404, 'Aluno não encontrado')
        def post(self):
            """Cria um novo check-in para um aluno."""
            data = request.get_json()
            if not data or 'id_aluno' not in data:
                api.abort(400, "Dados inválidos. id_aluno é obrigatório.")

            aluno_existe = Aluno.query.get(data['id_aluno'])
            if not aluno_existe:
                api.abort(
                    404, f"Aluno com ID {data['id_aluno']} não encontrado.")

            timestamp_checkin = data.get('timestamp_checkin')
            if timestamp_checkin:
                try:
                    timestamp_checkin = datetime.fromisoformat(
                        timestamp_checkin)
                except ValueError:
                    api.abort(
                        400, "Formato de timestamp_checkin inválido. Use ISO 8601 (AAAA-MM-DDTHH:MM:SS).")
            else:
                # Default para agora se não fornecido
                timestamp_checkin = datetime.now(timezone.utc)

            novo_checkin = Checkin(
                id_aluno=data['id_aluno'],
                timestamp_checkin=timestamp_checkin,
                duracao_minutos=data.get('duracao_minutos')
            )

            db.session.add(novo_checkin)
            db.session.commit()

            message_payload = {
                "checkin_id": novo_checkin.id,
                "id_aluno": novo_checkin.id_aluno,
                "timestamp": novo_checkin.timestamp_checkin.isoformat(),
                "type": "new_checkin_event"
            }
            publish_message("checkin_queue", message_payload)

            return novo_checkin, 201

    @ns_checkins.route('/<int:id>')
    @ns_checkins.response(404, 'Check-in não encontrado')
    class CheckinResource(Resource):
        @ns_checkins.doc('get_checkin')
        @ns_checkins.marshal_with(checkin_model)
        def get(self, id):
            """Retorna um check-in pelo seu ID."""
            checkin = Checkin.query.get_or_404(id)
            return checkin

        @ns_checkins.doc('update_checkin')
        @ns_checkins.expect(checkin_model)
        @ns_checkins.marshal_with(checkin_model)
        @ns_checkins.response(400, 'Dados inválidos')
        @ns_checkins.response(404, 'Aluno ou Check-in não encontrado')
        def put(self, id):
            """Atualiza um check-in existente."""
            checkin = Checkin.query.get_or_404(id)
            data = request.get_json()
            if not data:
                api.abort(400, "Dados inválidos.")

            if 'id_aluno' in data:
                aluno_existe = Aluno.query.get(data['id_aluno'])
                if not aluno_existe:
                    api.abort(
                        404, f"Aluno com ID {data['id_aluno']} não encontrado.")
                checkin.id_aluno = data['id_aluno']

            if 'timestamp_checkin' in data:
                timestamp_checkin = data.get('timestamp_checkin')
                if timestamp_checkin:
                    try:
                        checkin.timestamp_checkin = datetime.fromisoformat(
                            timestamp_checkin)
                    except ValueError:
                        api.abort(
                            400, "Formato de timestamp_checkin inválido. Use ISO 8601 (AAAA-MM-DDTHH:MM:SS).")
                else:
                    checkin.timestamp_checkin = None

            if 'duracao_minutos' in data:
                checkin.duracao_minutos = data['duracao_minutos']

            db.session.commit()
            return checkin

        @ns_checkins.doc('delete_checkin')
        @ns_checkins.response(204, 'Check-in deletado com sucesso')
        def delete(self, id):
            """Deleta um check-in pelo seu ID."""
            checkin = Checkin.query.get_or_404(id)
            db.session.delete(checkin)
            db.session.commit()
            return '', 204

    @ns_checkins.route('/bulk')
    class BulkCheckins(Resource):
        @ns_checkins.doc('bulk_checkins')
        @ns_checkins.expect(api.model('BulkCheckinsRequest', {'checkins': fields.List(fields.Nested(checkin_model), required=True, description='Lista de check-ins a serem criados em massa')}))
        @ns_checkins.response(201, 'Todos os check-ins em massa foram processados e enviados para fila.')
        @ns_checkins.response(207, 'Alguns check-ins não puderam ser processados.')
        @ns_checkins.response(400, 'Corpo da requisição deve ser uma lista de check-ins.')
        def post(self):
            """Cria múltiplos check-ins em massa."""
            data = request.get_json()
            if not data or not isinstance(data, list):
                api.abort(
                    400, "Corpo da requisição deve ser uma lista de check-ins.")

            processed_checkin_ids = []
            errors = []

            for checkin_data in data:
                try:
                    if 'id_aluno' not in checkin_data:
                        errors.append(
                            {"error": "id_aluno é obrigatório", "data": checkin_data})
                        continue

                    aluno_existe = Aluno.query.get(checkin_data['id_aluno'])
                    if not aluno_existe:
                        errors.append(
                            {"error": f"Aluno com ID {checkin_data['id_aluno']} não encontrado.", "data": checkin_data})
                        continue

                    timestamp_checkin = checkin_data.get('timestamp_checkin')
                    if timestamp_checkin:
                        try:
                            timestamp_checkin = datetime.fromisoformat(
                                timestamp_checkin)
                        except ValueError:
                            errors.append(
                                {"error": "Formato de timestamp_checkin inválido. Use ISO 8601.", "data": checkin_data})
                            continue
                    else:
                        timestamp_checkin = datetime.now(timezone.utc)

                    novo_checkin = Checkin(
                        id_aluno=checkin_data['id_aluno'],
                        timestamp_checkin=timestamp_checkin,
                        duracao_minutos=checkin_data.get('duracao_minutos')
                    )

                    db.session.add(novo_checkin)
                    db.session.commit()
                    processed_checkin_ids.append(novo_checkin.id)

                except Exception as e:
                    db.session.rollback()
                    errors.append({"error": str(e), "data": checkin_data})

            if processed_checkin_ids:
                message_payload = {
                    "checkin_ids": processed_checkin_ids,
                    "type": "bulk_checkin_event"
                }
                publish_message("checkin_queue", message_payload)

            if errors:
                return {
                    "message": "Alguns check-ins não puderam ser processados.",
                    "processed_ids": processed_checkin_ids,
                    "errors": errors
                }, 207
            else:
                return {
                    "message": "Todos os check-ins em massa foram processados e enviados para fila.",
                    "processed_ids": processed_checkin_ids
                }, 201

    # --- Rota para acionar o retreinamento do modelo de churn ---
    @ns_model.route('/retrain')
    class ModelRetrain(Resource):
        @ns_model.doc('trigger_model_retrain')
        @ns_model.response(200, 'Solicitação de retreinamento do modelo de churn enviada para a fila.')
        def post(self):
            """Envia uma mensagem para a fila para acionar o retreinamento do modelo de churn."""
            message_payload = {
                "type": "retrain_model_event"
            }
            publish_message("checkin_queue", message_payload)
            return {"message": "Solicitação de retreinamento do modelo de churn enviada para a fila."}, 200

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        pass
    app.run(debug=True)
