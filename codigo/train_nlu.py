import spacy
from spacy.tokens import DocBin
import random

# 1. Dados de Treinamento
# Formato: (texto, {"cats": {"INTENCAO": True/False, ...}})
TRAIN_DATA = [
    ("oi", {"cats": {"saudacao": True, "despedida": False, "perguntar_propriedade": False}}),
    ("olá", {"cats": {"saudacao": True, "despedida": False, "perguntar_propriedade": False}}),
    ("bom dia", {"cats": {"saudacao": True, "despedida": False, "perguntar_propriedade": False}}),

    ("tchau", {"cats": {"saudacao": False, "despedida": True, "perguntar_propriedade": False}}),
    ("adeus", {"cats": {"saudacao": False, "despedida": True, "perguntar_propriedade": False}}),
    ("até mais", {"cats": {"saudacao": False, "despedida": True, "perguntar_propriedade": False}}),

    ("Qual o material da parede P-10?", {"cats": {"saudacao": False, "despedida": False, "perguntar_propriedade": True}}),
    ("Do que é feito o pilar C-05?", {"cats": {"saudacao": False, "despedida": False, "perguntar_propriedade": True}}),
    ("me diga o material da laje L-01", {"cats": {"saudacao": False, "despedida": False, "perguntar_propriedade": True}}),
    ("para que serve a viga V-202", {"cats": {"saudacao": False, "despedida": False, "perguntar_propriedade": True}}),
    ("qual a função da parede interna 08", {"cats": {"saudacao": False, "despedida": False, "perguntar_propriedade": True}})
]

# 2. Criação do Modelo
nlp = spacy.blank("pt")  # Cria um pipeline em português em branco
category_pipe = nlp.add_pipe("textcat") # Adiciona o classificador de texto

# Adiciona os labels (intenções) ao pipe
category_pipe.add_label("saudacao")
category_pipe.add_label("despedida")
category_pipe.add_label("perguntar_propriedade")

# 3. Treinamento
optimizer = nlp.begin_training()
for i in range(10): # Número de épocas de treinamento
    random.shuffle(TRAIN_DATA)
    for text, annotations in TRAIN_DATA:
        doc = nlp.make_doc(text)
        example = spacy.training.Example.from_dict(doc, annotations)
        nlp.update([example], sgd=optimizer)

# 4. Salvar o modelo
nlp.to_disk("./nlu_model")
print("Modelo de NLU treinado e salvo em ./nlu_model")
