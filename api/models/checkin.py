# api/models/checkin.py

from api.database import db
from datetime import datetime

class Checkin(db.Model):
    __tablename__ = 'checkins' # Nome da tabela no banco de dados

    id = db.Column(db.Integer, primary_key=True)
    id_aluno = db.Column(db.Integer, db.ForeignKey('alunos.id'), nullable=False)
    # Adicionado nullable=False aqui, pois default=datetime.utcnow garante um valor.
    timestamp_checkin = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    duracao_minutos = db.Column(db.Integer, nullable=True) # duracao_minutos pode ser nulo se não informado

    # Se você ainda não adicionou o relacionamento para 'aluno' aqui no modelo Checkin, adicione:
    # aluno = db.relationship('Aluno', backref='checkins')
    # Isso é útil para acessar os dados do aluno a partir de um objeto Checkin (ex: checkin.aluno.nome)
    # E para que o 'backref' em Aluno (checkins = db.relationship('Checkin', backref='aluno', lazy=True)) funcione.

    def __repr__(self):
        return f"<Checkin Aluno:{self.id_aluno} em {self.timestamp_checkin}>"

    def to_dict(self):
        return {
            "id": self.id,
            "id_aluno": self.id_aluno,
            # Garante que timestamp_checkin.isoformat() só seja chamado se não for None
            # Embora com nullable=False e default, ele nunca deve ser None.
            "timestamp_checkin": self.timestamp_checkin.isoformat(),
            "duracao_minutos": self.duracao_minutos
        }