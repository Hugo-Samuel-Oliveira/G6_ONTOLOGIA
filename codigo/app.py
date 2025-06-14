from flask import Flask, request, jsonify, render_template, Response
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

RELATIONSHIP_KEYWORD_MAP = {
    # Relação Técnica: [Lista de palavras-chave únicas e fortes]
    'isContainedIn': ['onde', 'localização'],
    'hasMaterial': ['material', 'composição'],
    'aggregates': ['contém', 'agrega', 'partes'],
    'isOfType': ['tipo'], # Usaremos 'tipo' para a relação mais específica primeiro
    'type': ['classe']
}

# O mapa inverso agora pode ser gerado dinamicamente, mas por clareza vamos mantê-lo.
INVERSE_PROPERTY_MAP = {
    "inst:isContainedIn": "contêm o(a)",
    "inst:hasMaterial": "têm como material",
    "inst:aggregates": "são parte de",
    "inst:isOfType": "são do tipo",
    "rdf:type": "são instâncias da classe"
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
    # REGEX MAIS INTELIGENTE: Procura por um padrão que indica explicitamente o objeto.
    # Prioriza frases como "do 'objeto'" ou "para o objeto 'objeto'".
    explicit_match = re.search(r"(?:para o objeto|do|da|de|para)\s+('([^']*)'|\"([^\"]*)\")", text, re.IGNORECASE)
    if explicit_match:
        # O grupo 2 captura o que está dentro das aspas simples, o grupo 3 o que está nas duplas.
        return explicit_match.group(2) or explicit_match.group(3)

    # FALLBACK: Se não encontrar o padrão explícito, tenta pegar a primeira ocorrência entre aspas.
    # Isso mantém a compatibilidade com perguntas mais simples.
    fallback_match = re.search(r"'([^']*)'|\"([^\"]*)\"", text)
    if fallback_match:
        return fallback_match.group(1) or fallback_match.group(2)

    return None # Retorna None se nenhum padrão for encontrado.

def extract_bim_property(text):
    # Lida com perguntas geradas pelo Construtor de Consultas
    match = re.search(r"relação '([^']*)'", text, re.IGNORECASE)
    if match:
        return match.group(1)

    # Nova lógica: busca por palavras-chave únicas e fortes
    text_lower = text.lower()
    user_words = set(text_lower.split())

    # A ordem aqui importa. Verificamos 'isOfType' antes de 'type'.
    relations_in_order = ['isOfType', 'type', 'isContainedIn', 'hasMaterial', 'aggregates']

    for technical_relation in relations_in_order:
        keywords = RELATIONSHIP_KEYWORD_MAP.get(technical_relation, [])
        # Verifica se ALGUMA das palavras-chave está na pergunta do usuário
        if any(word in user_words for word in keywords):
            return technical_relation
            
    # Se nenhuma palavra-chave for encontrada, retorna 'label'
    return "label"

def query_bim_property(object_name, predicate_label):
    if not object_name:
        return "Não consegui identificar sobre qual elemento você está perguntando."

    if predicate_label == 'type':
        predicate = 'rdf:type'
    elif predicate_label == 'label':
        predicate = 'rdfs:label'
    else:
        predicate = f'inst:{predicate_label}'

    sparql = SPARQLWrapper(FUSEKI_ENDPOINT)
    sparql.setReturnFormat(JSON)

    try:
        # --- ETAPA 1: Busca exclusivamente por TODAS as relações de SAÍDA ---
        query_outgoing = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX inst: <{BASE_URI}>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT DISTINCT ?valueLabel WHERE {{
                ?element rdfs:label "{object_name}" .
                ?element {predicate} ?value .
                ?value rdfs:label ?valueLabel .
            }}
        """
        sparql.setQuery(query_outgoing)
        results = sparql.query().convert()["results"]["bindings"]

        if results:
            values = [item["valueLabel"]["value"] for item in results]
            count = len(values)
            return (f"✅ Relação de Saída ({count} resultado(s)): A propriedade '{predicate_label}' para '{object_name}' é: "
                    f"{', '.join(f"'{v}'" for v in values)}.")

        # --- ETAPA 2: Se não houver saída, busca exclusivamente por TODAS as relações de ENTRADA ---
        query_incoming = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX inst: <{BASE_URI}>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT DISTINCT ?subjectLabel WHERE {{
                ?object rdfs:label "{object_name}" .
                ?subject {predicate} ?object .
                ?subject rdfs:label ?subjectLabel .
            }}
        """
        sparql.setQuery(query_incoming)
        inverse_results = sparql.query().convert()["results"]["bindings"]

        if inverse_results:
            subjects = [item["subjectLabel"]["value"] for item in inverse_results]
            count = len(subjects)
            inverse_relation_phrase = INVERSE_PROPERTY_MAP.get(predicate, f"têm a relação '{predicate_label}' para")
            return (f"➡️ Relação de Entrada ({count} resultado(s)): Os seguintes objetos {inverse_relation_phrase} '{object_name}': "
                    f"{', '.join(f"'{s}'" for s in subjects)}.")

    except Exception as e:
        return f"Erro na consulta SPARQL: {e}"

    # --- ETAPA 3: Se ambas as buscas falharem ---
    return f"❌ Desculpe, não encontrei a propriedade '{predicate_label}' para o objeto '{object_name}', nem relações de entrada ou saída correspondentes."

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
    if not object_name:
        return jsonify({"nodes": [], "edges": []})

    sparql = SPARQLWrapper(FUSEKI_ENDPOINT)
    sparql.setReturnFormat(JSON)

    # A consulta SPARQL continua a mesma
    query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX inst: <{BASE_URI}>
        SELECT DISTINCT ?s ?s_label ?p_label ?o ?o_label
        WHERE {{
            BIND("{object_name}" AS ?target_label)
            {{ ?s rdfs:label ?target_label. ?s ?p ?o. }}
            UNION
            {{ ?o rdfs:label ?target_label. ?s ?p ?o. }}
            
            ?s rdfs:label ?s_label.
            ?o rdfs:label ?o_label.
            BIND(REPLACE(STR(?p), ".*[/#]", "") AS ?p_label)
            FILTER(isIRI(?o) && isIRI(?s))
        }}
    """

    nodes, edges, node_ids = [], [], set()

    try:
        sparql.setQuery(query)
        results = sparql.query().convert()

        # --- LÓGICA DE COLORAÇÃO MODIFICADA ---
        central_node_color = "#a3e635"  # Verde para o nó principal
        related_node_color = "#93c5fd"  # Azul para os nós relacionados
        
        for res in results.get("results", {}).get("bindings", []):
            s_uri = res['s']['value']
            s_label = res['s_label']['value']
            o_uri = res['o']['value']
            o_label = res.get('o_label', {}).get('value', o_uri.split('#')[-1])

            # Adiciona o nó de origem (subject)
            if s_uri not in node_ids:
                is_central = s_label == object_name
                color = central_node_color if is_central else related_node_color
                size = 25 if is_central else 15
                nodes.append({"id": s_uri, "label": s_label, "color": color, "size": size})
                node_ids.add(s_uri)

            # Adiciona o nó de destino (object)
            if o_uri not in node_ids:
                is_central = o_label == object_name
                color = central_node_color if is_central else related_node_color
                size = 25 if is_central else 15
                nodes.append({"id": o_uri, "label": o_label, "color": color, "size": size})
                node_ids.add(o_uri)

            edges.append({"from": s_uri, "to": o_uri, "label": res['p_label']['value']})

    except Exception as e:
        print(f"Erro ao gerar dados do grafo: {e}")

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

@app.route('/ontology-summary')
def get_ontology_summary():
    sparql = SPARQLWrapper(FUSEKI_ENDPOINT)
    sparql.setReturnFormat(JSON)

    # Consulta para buscar todos os tipos de objetos e exemplos
    query_types = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX inst: <{BASE_URI}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT ?type_label (GROUP_CONCAT(DISTINCT ?example_label; SEPARATOR=", ") AS ?examples)
        WHERE {{
            ?s a ?type .
            ?s rdfs:label ?example_label .
            ?type rdfs:label ?type_label .
            # Filtra para pegar apenas tipos definidos em nossa ontologia
            FILTER(STRSTARTS(STR(?type), STR(inst:)))
        }} GROUP BY ?type_label ORDER BY ?type_label
    """

    # --- CONSULTA DE RELAÇÕES APRIMORADA ---
    # Esta consulta agora busca DINAMICAMENTE todos os predicados (relações)
    query_relations = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX inst: <{BASE_URI}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT DISTINCT ?p_label WHERE {{
            ?s ?p ?o .
            # Filtro para garantir que a relação conecte duas entidades, não uma entidade a um valor literal (como um nome)
            FILTER(isIRI(?s) && isIRI(?p) && isIRI(?o))

            # Filtro para excluir predicados muito genéricos do RDF/RDFS que não são úteis ao usuário
            FILTER(!STRSTARTS(STR(?p), STR(rdfs:)))
            
            BIND(REPLACE(STR(?p), ".*[/#]", "") AS ?p_label)
        }} ORDER BY ?p_label
    """

    try:
        sparql.setQuery(query_types)
        types_results = sparql.query().convert()

        sparql.setQuery(query_relations)
        relations_results = sparql.query().convert()

        types = [
            {"type": res['type_label']['value'], "examples": res['examples']['value'].split(', ')}
            for res in types_results["results"]["bindings"]
        ]
        
        # Extrai apenas o label da relação para a lista
        relations = [res['p_label']['value'] for res in relations_results["results"]["bindings"]]
        
        # Adiciona 'type' manualmente caso não seja capturado, pois é uma relação fundamental (rdf:type)
        if 'type' not in relations:
            relations.insert(0, 'type')
        
        return jsonify({"types": types, "relations": relations})

    except Exception as e:
        print(f"Erro ao buscar resumo da ontologia: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    if not os.path.exists(NLU_MODEL_PATH):
        print("!!! ATENÇÃO: Modelo de NLU não encontrado.")
        print("!!! Execute 'python setup.py' para criar os modelos e dados necessários.")
    else:
        app.run(host='0.0.0.0', port=5000, debug=False)
