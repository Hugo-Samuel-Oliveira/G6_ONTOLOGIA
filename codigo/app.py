from flask import Flask, request, jsonify, render_template
import spacy
from SPARQLWrapper import SPARQLWrapper, JSON
import re
import os
import json

app = Flask(__name__)

# --- Configurações e Mapeamento ---
FUSEKI_ENDPOINT = os.environ.get("FUSEKI_ENDPOINT", "http://localhost:3030/BIM_Knowledge_Base/query")
NLU_MODEL_PATH = "./nlu_model"
BASE_URI = "http://exemplo.org/bim#"
PROPERTY_MAP = {
    "material": "inst:hasMaterial", "composição": "inst:hasMaterial", "feito de": "inst:hasMaterial",
    "onde está": "inst:isContainedIn", "localização": "inst:isContainedIn", "parte de": "inst:isContainedIn",
    "tipo": "inst:isOfType", "tipo de": "inst:isOfType",
    "agrega": "inst:aggregates", "contém": "inst:aggregates",
    "classe": "rdf:type", "nome": "rdfs:label",
}

# --- Carregamento do Modelo NLU ---
nlp = None
try:
    nlp = spacy.load(NLU_MODEL_PATH)
    print("-> Modelo de NLU carregado com sucesso.")
except IOError:
    print(f"-> ALERTA: Modelo de NLU não encontrado. Execute 'python setup.py' primeiro.")

# --- Funções de Lógica do Chatbot ---
def get_intent(text):
    if not nlp: return "error"
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
    predicate = PROPERTY_MAP.get(property_keyword, "rdfs:label")

    sparql = SPARQLWrapper(FUSEKI_ENDPOINT)
    sparql.setReturnFormat(JSON)
    query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX inst: <{BASE_URI}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
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
            value = bindings[0]["valueLabel"]["value"].split('#')[-1]
            return f"A propriedade '{property_keyword}' de '{object_name}' é: {value}."
        else:
            return f"Desculpe, não encontrei a propriedade '{property_keyword}' para o objeto '{object_name}'."
    except Exception as e:
        return f"Erro na consulta SPARQL: {e}"

# --- Endpoints da Aplicação ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try: data = request.get_json(force=True); user_message = data.get("message")
    except Exception: return jsonify({"error": "JSON inválido"}), 400
    if not user_message: return jsonify({"error": "Mensagem não fornecida."}), 400

    intent = get_intent(user_message)
    response_text = "Desculpe, não entendi o que você quis dizer."
    bim_object = None; bim_property = None; action = None

    if intent == "saudacao": response_text = "Olá! Sou seu assistente BIM. Como posso ajudar?"
    elif intent == "despedida": response_text = "Até mais!"
    elif intent == "perguntar_propriedade":
        bim_object = extract_bim_object(user_message)
        bim_property = extract_bim_property(user_message)
        response_text = query_bim_property(bim_object, bim_property)
    elif intent == "grafo_completo":
        response_text = "OK. Gerando o grafo completo da ontologia..."
        action = "full_graph"
    return jsonify({"response": response_text, "object": bim_object, "property": bim_property, "action": action})


@app.route('/graph-data')
def get_graph_data():
    object_name = request.args.get('object_name')
    if not object_name: return jsonify({"nodes": [], "edges": []})

    sparql = SPARQLWrapper(FUSEKI_ENDPOINT)
    sparql.setReturnFormat(JSON)
    # Query que busca tanto relações de entrada quanto de saída para o objeto
    query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX inst: <{BASE_URI}>
        SELECT DISTINCT ?s ?s_label ?p_label ?o ?o_label
        WHERE {{
            BIND("{object_name}" AS ?target_label)
            {{
                ?s rdfs:label ?target_label .
                ?s ?p ?o .
            }} UNION {{
                ?o rdfs:label ?target_label .
                ?s ?p ?o .
            }}
            ?s rdfs:label ?s_label .
            ?o rdfs:label ?o_label .
            BIND(REPLACE(STR(?p), ".*[/#]", "") AS ?p_label)
            FILTER(isIRI(?o) && isIRI(?s))
        }}
    """
    nodes, edges, node_ids = [], [], set()
    try:
        sparql.setQuery(query)
        results = sparql.query().convert()
        for res in results.get("results", {}).get("bindings", []):
            s_uri = res['s']['value']; s_label = res['s_label']['value']
            o_uri = res['o']['value']; o_label = res.get('o_label', {}).get('value', o_uri.split('#')[-1])
            
            # Adiciona os nós (sujeito e objeto)
            if s_uri not in node_ids:
                is_central = s_label == object_name
                nodes.append({"id": s_uri, "label": s_label, "color": "#a3e635" if is_central else "#93c5fd", "size": 25 if is_central else 15});
                node_ids.add(s_uri)
            if o_uri not in node_ids:
                is_central = o_label == object_name
                nodes.append({"id": o_uri, "label": o_label, "color": "#a3e635" if is_central else "#93c5fd", "size": 25 if is_central else 15});
                node_ids.add(o_uri)
            
            # Adiciona a aresta
            edges.append({"from": s_uri, "to": o_uri, "label": res['p_label']['value']})
    except Exception as e: print(f"Erro ao gerar dados do grafo: {e}")
    return jsonify({"nodes": nodes, "edges": edges})

@app.route('/full-graph-data')
def get_full_graph_data():
    sparql = SPARQLWrapper(FUSEKI_ENDPOINT)
    sparql.setReturnFormat(JSON)
    query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX inst: <{BASE_URI}>
        SELECT ?s_label ?p_label ?o_label ?s ?o
        WHERE {{
            ?s ?p ?o .
            FILTER (STRSTARTS(STR(?s), STR(inst:)) && isIRI(?o) && STRSTARTS(STR(?o), STR(inst:)))
            ?s rdfs:label ?s_label .
            ?o rdfs:label ?o_label .
            BIND(REPLACE(STR(?p), ".*[/#]", "") AS ?p_label)
        }}
        LIMIT 150
    """
    nodes, edges, node_ids = [], [], set()
    try:
        sparql.setQuery(query)
        results = sparql.query().convert()
        for res in results.get("results", {}).get("bindings", []):
            s_uri = res['s']['value']; s_label = res['s_label']['value']
            if s_uri not in node_ids: nodes.append({"id": s_uri, "label": s_label}); node_ids.add(s_uri)
            o_uri = res['o']['value']; o_label = res['o_label']['value']
            if o_uri not in node_ids: nodes.append({"id": o_uri, "label": o_label}); node_ids.add(o_uri)
            edges.append({"from": s_uri, "to": o_uri, "label": res['p_label']['value']})
    except Exception as e: print(f"Erro ao gerar grafo completo: {e}")
    return jsonify({"nodes": nodes, "edges": edges})


if __name__ == '__main__':
    if not os.path.exists(NLU_MODEL_PATH):
        print("!!! ATENÇÃO: Modelo de NLU não encontrado.")
        print("!!! Execute 'python setup.py' para criar os modelos e dados necessários.")
    else:
        app.run(host='0.0.0.0', port=5000, debug=False)

