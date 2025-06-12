import spacy
from spacy.training.example import Example
import random

# Dados de Treinamento para classificação de intenção
TRAIN_DATA = [
    ("oi", {"cats": {"saudacao": 1.0, "despedida": 0.0, "perguntar_propriedade": 0.0}}),
    ("olá", {"cats": {"saudacao": 1.0, "despedida": 0.0, "perguntar_propriedade": 0.0}}),
    ("tchau", {"cats": {"saudacao": 0.0, "despedida": 1.0, "perguntar_propriedade": 0.0}}),
    ("adeus", {"cats": {"saudacao": 0.0, "despedida": 1.0, "perguntar_propriedade": 0.0}}),
    ("Qual o material da parede P-10?", {"cats": {"saudacao": 0.0, "despedida": 0.0, "perguntar_propriedade": 1.0}}),
    ("Do que é feito o 'pilar C-05'?", {"cats": {"saudacao": 0.0, "despedida": 0.0, "perguntar_propriedade": 1.0}}),
    ("me diga a composição da laje L-01", {"cats": {"saudacao": 0.0, "despedida": 0.0, "perguntar_propriedade": 1.0}})
]

# Cria um pipeline em português em branco
nlp = spacy.blank("pt")
# Adiciona o componente 'textcat' para classificação de texto
textcat = nlp.add_pipe("textcat")

# Adiciona os labels (intenções) ao componente
textcat.add_label("saudacao")
textcat.add_label("despedida")
textcat.add_label("perguntar_propriedade")

# Inicia o treinamento
optimizer = nlp.initialize()
for i in range(10): # Número de épocas de treinamento
    random.shuffle(TRAIN_DATA)
    losses = {}
    for text, annotations in TRAIN_DATA:
        doc = nlp.make_doc(text)
        example = Example.from_dict(doc, annotations)
        nlp.update([example], drop=0.5, losses=losses)
    print(f"Losses na época {i}: {losses}")

# Salva o modelo treinado
nlp.to_disk("./nlu_model")
print("Modelo de NLU treinado e salvo em ./nlu_model")