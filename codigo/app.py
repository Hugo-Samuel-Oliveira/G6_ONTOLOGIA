from flask import Flask, request, jsonify, render_template
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
PROPERTY_MAP = {
    "material": "inst:hasMaterial",
    "composição": "inst:hasMaterial",
    "feito de": "inst:hasMaterial",
    "nome": "rdfs:label",
}

# --- Carregar modelo NLU ---
try:
    nlp = spacy.load(NLU_MODEL_PATH)
    print("Modelo de NLU carregado com sucesso.")
except IOError:
    print(f"Erro: Modelo não encontrado em {NLU_MODEL_PATH}. Execute train_nlu.py primeiro.")
    nlp = None

# --- Funções de Lógica ---
def get_intent(text):
    if not nlp: return None
    doc = nlp(text)
    return max(doc.cats, key=doc.cats.get)

def extract_bim_object(text):
    match = re.search(r"'(.*?)'|\"([^\"]*)\"", text)
    if match: return match.group(1) or match.group(2)
    match = re.search(r"\b(da|do|o|a)\s+([\w\s\d\-]+)", text, re.IGNORECASE)
    if match:
        object_name = match.group(2).strip()
        return object_name[:-1].strip() if object_name.endswith('?') else object_name
    return None

def extract_bim_property(text):
    text_lower = text.lower()
    for prop_keyword in PROPERTY_MAP.keys():
        if prop_keyword in text_lower:
            return prop_keyword
    return "nome"

def query_bim_property(object_name, property_keyword):
    if not object_name: return "Não consegui identificar sobre qual elemento você está perguntando."
    predicate = PROPERTY_MAP.get(property_keyword)
    if not predicate: return f"Não sei como consultar a propriedade '{property_keyword}'."

    sparql = SPARQLWrapper(FUSEKI_ENDPOINT)
    sparql.setReturnFormat(JSON)
    query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX inst: <http://exemplo.org/bim#>
        SELECT ?valueLabel WHERE {{
            ?element rdfs:label "{object_name}" .
            ?element {predicate} ?value .
            OPTIONAL {{ ?value rdfs:label ?valueLabelFromResource . }}
            BIND(COALESCE(?valueLabelFromResource, STR(?value)) AS ?valueLabel)
        }} LIMIT 1
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
        print(f"Erro na consulta SPARQL: {e}")
        return "Ocorreu um erro ao buscar a informação na base de conhecimento."

# --- Endpoints da API ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get("message")
    except Exception:
        raw_data = request.get_data()
        try:
            decoded_data = raw_data.decode('utf-8')
        except UnicodeDecodeError:
            decoded_data = raw_data.decode('latin-1', errors='ignore')
        data = json.loads(decoded_data)
        user_message = data.get("message")

    if not user_message:
        return jsonify({"error": "Mensagem não fornecida."}), 400

    intent = get_intent(user_message)
    response_text = "Desculpe, não entendi o que você quis dizer."
    bim_object = None

    if intent == "saudacao":
        response_text = "Olá! Sou seu assistente BIM. Como posso ajudar?"
    elif intent == "despedida":
        response_text = "Até mais!"
    elif intent == "perguntar_propriedade":
        bim_object = extract_bim_object(user_message)
        bim_property = extract_bim_property(user_message)
        response_text = query_bim_property(bim_object, bim_property)

    return jsonify({"response": response_text, "object": bim_object})

@app.route('/graph-data')
def get_graph_data():
    """Fornece dados do sub-grafo de um objeto para visualização."""
    object_name = request.args.get('object_name')
    if not object_name:
        return jsonify({"nodes": [], "edges": []})

    sparql = SPARQLWrapper(FUSEKI_ENDPOINT)
    sparql.setReturnFormat(JSON)
    
    # Query para obter o elemento principal e suas relações diretas
    query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX inst: <http://exemplo.org/bim#>

        SELECT ?element ?p ?relatedElement ?relatedName
        WHERE {{
            ?element rdfs:label "{object_name}" .
            ?element ?p ?relatedElement .
            FILTER(STRSTARTS(STR(?p), STR(inst:)))
            FILTER(isIRI(?relatedElement))
            OPTIONAL {{ ?relatedElement rdfs:label ?relatedName . }}
        }}
    """
    
    nodes, edges = [], []
    node_ids = set()
    
    try:
        sparql.setQuery(query)
        results = sparql.query().convert()
        bindings = results.get("results", {}).get("bindings", [])

        if not bindings:
            print(f"Alerta: A consulta SPARQL para o grafo de '{object_name}' não retornou resultados.")
            return jsonify({"nodes": [], "edges": []})

        # Adiciona o nó central primeiro
        central_node_uri = bindings[0]['element']['value']
        if central_node_uri not in node_ids:
            nodes.append({"id": central_node_uri, "label": object_name})
            node_ids.add(central_node_uri)

        # Itera sobre as relações
        for res in bindings:
            related_node_uri = res['relatedElement']['value']
            if related_node_uri not in node_ids:
                # Usa o label encontrado ou um fallback
                related_label = res.get('relatedName', {}).get('value', related_node_uri.split('#')[-1])
                nodes.append({"id": related_node_uri, "label": related_label})
                node_ids.add(related_node_uri)
            
            prop_uri = res['p']['value']
            prop_label = prop_uri.split('#')[-1]
            edges.append({"from": central_node_uri, "to": related_node_uri, "label": prop_label})

    except Exception as e:
        print(f"Erro ao gerar dados do grafo: {e}")

    return jsonify({"nodes": nodes, "edges": edges})

if __name__ == '__main__':
    app.run(debug=True, port=5000)