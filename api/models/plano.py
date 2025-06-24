    # api/models/plano.py

from ..database import db

class Plano(db.Model):
    __tablename__ = 'planos'
    id = db.Column(db.Integer, primary_key=True)
    nome_plano = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Numeric(10, 2), nullable=False)
    descricao = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Plano {self.nome_plano}>"

    # Adicione este método para serializar o objeto
    def to_dict(self):
        return {
            "id": self.id,
            "nome_plano": self.nome_plano,
            "preco": str(self.preco), # Converta Decimal para string
            "descricao": self.descricao
        }