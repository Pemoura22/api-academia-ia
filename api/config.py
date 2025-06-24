# api/config.py

class Config:
    # Configurações do banco de dados PostgreSQL
    # Certifique-se de que os detalhes do seu banco (usuário, senha, host, porta, nome do DB) estão corretos.
    # Adicionando '?charset=utf8' para garantir a codificação.
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:Tobias280722%40@127.0.0.1:5432/gym_db?options=-c%20client_encoding%3DUTF8'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = '89ab01cd23ef456789ab01cd23ef456789ab01cd23ef4567' # Substitua por uma chave secreta forte para produção
