from flask import Flask, request, jsonify
import spacy
from SPARQLWrapper import SPARQLWrapper, JSON
import re
import os
import json

app = Flask(__name__)

# --- Configurações ---
FUSEKI_ENDPOINT = os.environ.get("FUSEKI_ENDPOINT", "http://localhost:3030/BIM_Knowledge_Base/sparql")
NLU_MODEL_PATH = "./nlu_model"

# --- Mapeamento Semântico ---
# Mapeia termos da linguagem natural para predicados da ontologia
PROPERTY_MAP = {
    "material": "inst:hasMaterial",
    "composição": "inst:hasMaterial",
    "feito de": "inst:hasMaterial",
    "nome": "rdfs:label",
    # Adicione outras propriedades aqui, como "função", "comprimento", etc.
    # "função": "inst:hasFunction" 
}

# --- Carregar o modelo de NLU ---
try:
    nlp = spacy.load(NLU_MODEL_PATH)
    print("Modelo de NLU carregado com sucesso.")
except IOError:
    print(f"Erro: Modelo não encontrado em {NLU_MODEL_PATH}. Execute train_nlu.py primeiro.")
    nlp = None

# --- Funções de Lógica ---

def get_intent(text):
    """Usa o modelo spaCy para classificar a intenção do texto."""
    if not nlp:
        return None
    doc = nlp(text)
    return max(doc.cats, key=doc.cats.get)

def extract_bim_object(text):
    """Extrai o nome do objeto BIM, priorizando texto entre aspas."""
    match = re.search(r"'(.*?)'|\"([^\"]*)\"", text)
    if match:
        return match.group(1) or match.group(2)
    match = re.search(r"\b(da|do|o|a)\s+([\w\s\d\-]+)", text, re.IGNORECASE)
    if match:
        object_name = match.group(2).strip()
        if object_name.endswith('?'):
            return object_name[:-1].strip()
        return object_name
    return None

def extract_bim_property(text):
    """Extrai a propriedade que o usuário está perguntando."""
    text_lower = text.lower()
    for prop_keyword in PROPERTY_MAP.keys():
        if prop_keyword in text_lower:
            return prop_keyword
    return "nome" # Retorna 'nome' como propriedade padrão se nada for encontrado

def query_bim_property(object_name, property_keyword):
    """Executa uma consulta SPARQL genérica para obter uma propriedade de um objeto."""
    if not object_name:
        return "Não consegui identificar sobre qual elemento você está perguntando. Tente colocar o nome do objeto entre aspas, como 'floor'."

    # Obtém o predicado da ontologia a partir do nosso mapa semântico
    predicate = PROPERTY_MAP.get(property_keyword)
    if not predicate:
        return f"Não sei como consultar a propriedade '{property_keyword}'."

    sparql = SPARQLWrapper(FUSEKI_ENDPOINT)
    sparql.setReturnFormat(JSON)

    # A consulta agora é dinâmica com base no predicado
    query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX inst: <http://exemplo.org/bim#>

        SELECT ?valueLabel WHERE {{
            ?element rdfs:label "{object_name}" .
            ?element {predicate} ?value .
            # Se o valor for um recurso (URI), busca seu label. Caso contrário, usa o valor literal.
            OPTIONAL {{ ?value rdfs:label ?valueLabelFromResource . }}
            BIND(COALESCE(?valueLabelFromResource, ?value) AS ?valueLabel)
        }}
        LIMIT 1
    """
    
    try:
        sparql.setQuery(query)
        results = sparql.query().convert()
        bindings = results["results"]["bindings"]
        
        if bindings:
            value = bindings[0]["valueLabel"]["value"]
            return f"A propriedade '{property_keyword}' de '{object_name}' é: {value}."
        else:
            return f"Desculpe, não encontrei a propriedade '{property_keyword}' para o objeto '{object_name}'."
    except Exception as e:
        print(f"Erro ao consultar o Fuseki: {e}")
        return "Ocorreu um erro ao tentar buscar a informação."

# --- Endpoint da API ---

@app.route('/chat', methods=['POST'])
def chat():
    """Endpoint principal para receber mensagens e retornar respostas."""
    try:
        # Pega os bytes brutos da requisição
        raw_data = request.get_data()
        # Tenta decodificar como UTF-8, que é o padrão para JSON
        decoded_data = raw_data.decode('utf-8')
    except UnicodeDecodeError:
        # Se falhar, tenta um fallback comum para terminais Windows (latin-1)
        print("Alerta: Falha na decodificação UTF-8. Usando 'latin-1' como fallback.")
        decoded_data = raw_data.decode('latin-1')

    try:
        data = json.loads(decoded_data)
        message = data.get("message")
    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar JSON: {e}")
        return jsonify({"error": f"Falha ao decodificar o objeto JSON: {e}"}), 400

    if not message:
        return jsonify({"error": "Mensagem não fornecida."}), 400

    intent = get_intent(message)
    response_text = "Desculpe, não entendi o que você quis dizer."

    if intent == "saudacao":
        response_text = "Olá! Sou seu assistente BIM. Como posso ajudar?"
    elif intent == "despedida":
        response_text = "Até mais!"
    elif intent == "perguntar_propriedade":
        bim_object = extract_bim_object(message)
        bim_property = extract_bim_property(message)
        response_text = query_bim_property(bim_object, bim_property)

    return jsonify({"response": response_text})

# --- Execução do Servidor ---

if __name__ == '__main__':
    app.run(debug=True, port=5000)
