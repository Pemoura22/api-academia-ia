# churn_model.py

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os


class ChurnPredictor:
    def __init__(self, model_path="churn_model.joblib"):
        self.model = None
        self.model_path = model_path
        self.features = ['frequencia_semanal', 'dias_desde_ultimo_checkin',
                         'duracao_media_visitas_minutos', 'tipo_plano_encoded']
        self.load_model()

    def create_dummy_data(self):
        """
        Cria um conjunto de dados de exemplo para treinar o modelo.
        Em um cenário real, estes dados viriam do seu banco de dados.
        Para simular um "retreinamento com novos dados", podemos adicionar um pouco de variância.
        """
        data = {
            'frequencia_semanal': [5, 4, 1, 0.5, 3, 2, 0, 6, 1.5, 0.2, 4.5, 3.8, 0.8, 0, 5, 2.5, 1.2, 3.1],
            'dias_desde_ultimo_checkin': [1, 5, 10, 20, 3, 7, 40, 2, 15, 60, 4, 6, 25, 90, 8, 12, 18, 5],
            'duracao_media_visitas_minutos': [60, 55, 40, 25, 70, 50, 20, 65, 35, 15, 75, 68, 28, 10, 80, 48, 33, 62],
            'tipo_plano_encoded': [1, 2, 1, 1, 3, 2, 1, 3, 1, 1, 2, 3, 1, 1, 3, 2, 1, 3],
            # Adicionado alguns novos exemplos
            'churn': [0, 0, 0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 0]
        }
        df = pd.DataFrame(data)
        return df

    def train_model(self, X, y):
        """
        Treina o modelo de Regressão Logística.
        """
        print(" [ML] Treinando o modelo de previsão de churn...")
        self.model = LogisticRegression(solver='liblinear', random_state=42)
        self.model.fit(X, y)
        print(" [ML] Modelo treinado com sucesso!")
        self.save_model()

    def load_model(self):
        """
        Carrega um modelo treinado do disco, se existir.
        """
        if os.path.exists(self.model_path):
            print(
                f" [ML] Carregando modelo de churn de '{self.model_path}'...")
            self.model = joblib.load(self.model_path)
            print(" [ML] Modelo carregado.")
        else:
            # Se o modelo não existe, treinamos um novo
            print(
                " [ML] Modelo não encontrado. Treinando um novo modelo na inicialização.")
            df = self.create_dummy_data()
            X = df[self.features]
            y = df['churn']
            self.train_model(X, y)

    def save_model(self):
        """
        Salva o modelo treinado no disco.
        """
        if self.model:
            joblib.dump(self.model, self.model_path)
            print(f" [ML] Modelo salvo em '{self.model_path}'.")

    def retrain_and_save_model(self):
        """
        Simula o retreinamento do modelo com novos dados (dummy data atualizado) e o salva.
        """
        print(" [ML] Acionando retreinamento do modelo de churn...")
        # Em um cenário real, você buscaria novos dados do banco de dados aqui.
        new_df = self.create_dummy_data()
        X_new = new_df[self.features]
        y_new = new_df['churn']
        self.train_model(X_new, y_new)  # Reutiliza a função de treino
        print(" [ML] Retreinamento concluído e modelo salvo.")

    def predict_churn_probability(self, features_data):
        """
        Prevê a probabilidade de churn para um dado conjunto de características.
        """
        if not self.model:
            self.load_model()

        if not self.model:
            print(" [ERROR] Modelo de churn não disponível para previsão.")
            return None

        input_df = pd.DataFrame([features_data], columns=self.features)

        probability = self.model.predict_proba(input_df)[:, 1][0]
        return probability


# Exemplo de como usar a classe:
if __name__ == '__main__':
    predictor = ChurnPredictor()

    aluno_metrics = {
        'frequencia_semanal': 0.5,
        'dias_desde_ultimo_checkin': 25,
        'duracao_media_visitas_minutos': 20,
        'tipo_plano_encoded': 1
    }

    churn_prob = predictor.predict_churn_probability(aluno_metrics)
    if churn_prob is not None:
        print(
            f"\n [PREVISÃO] A probabilidade de churn para o aluno é: {churn_prob:.2f}")
        if churn_prob >= 0.5:
            print(" [PREVISÃO] Alto risco de Churn!")
        else:
            print(" [PREVISÃO] Baixo risco de Churn.")

    aluno_metrics_baixo_risco = {
        'frequencia_semanal': 4,
        'dias_desde_ultimo_checkin': 2,
        'duracao_media_visitas_minutos': 60,
        'tipo_plano_encoded': 2
    }
    churn_prob_baixo = predictor.predict_churn_probability(
        aluno_metrics_baixo_risco)
    if churn_prob_baixo is not None:
        print(
            f"\n [PREVISÃO] A probabilidade de churn para o aluno (baixo risco) é: {churn_prob_baixo:.2f}")
