# api/database.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app):
    """
    Inicializa a extensão SQLAlchemy com a aplicação Flask.
    """
    db.init_app(app)
    # Se você precisar criar tabelas automaticamente ao iniciar a aplicação
    # (por exemplo, em ambiente de desenvolvimento, ou se não usa migrações),
    # você pode descomentar a linha abaixo.
    # No entanto, em produção, é mais comum usar ferramentas de migração de banco de dados (ex: Flask-Migrate).
    # db.create_all()
