# api/models/aluno.py

from api.database import db
from datetime import datetime

class Aluno(db.Model):
    __tablename__ = 'alunos' # Nome da tabela no banco de dados

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    data_nascimento = db.Column(db.Date) # Pode ser nulo
    id_plano = db.Column(db.Integer, db.ForeignKey('planos.id'), nullable=False) # Aluno deve ter um plano
    data_matricula = db.Column(db.DateTime, default=datetime.utcnow, nullable=False) # Usar utcnow para timestamps consistentes, não nulo
    status = db.Column(db.String(50), default='ativo', nullable=False) # Status padrão 'ativo', não nulo

    # Relação com a tabela Checkin
    checkins = db.relationship('Checkin', backref='aluno', lazy=True)
    # Relação com a tabela Plano (para acessar dados do plano do aluno)
    plano = db.relationship('Plano', backref='alunos', lazy=True)


    def __repr__(self):
        return f"<Aluno {self.nome} ({self.email})>"

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "email": self.email,
            "data_nascimento": self.data_nascimento.isoformat() if self.data_nascimento else None, # Preferível isoformat() para JSON
            "id_plano": self.id_plano,
            "data_matricula": self.data_matricula.isoformat(), # isoformat() para DateTime
            "status": self.status
        }