from flask import Flask, request, jsonify, render_template, Response
import spacy  # Para carregar e usar o modelo de NLU pré-treinado.
from SPARQLWrapper import SPARQLWrapper, JSON  # Para se conectar e fazer consultas ao servidor SPARQL (Fuseki).
import re  # Para usar expressões regulares na extração de texto.
import os  # Para interagir com o sistema de arquivos (verificar caminhos).
import json # Embora não usado diretamente, é bom ter para manipulação de JSON.

# Inicializa a aplicação Flask.
app = Flask(__name__)

# --- Configurações Globais e Mapeamentos ---
# Define o endpoint do servidor Fuseki. Usa uma variável de ambiente se existir, senão usa o padrão.
FUSEKI_ENDPOINT = os.environ.get("FUSEKI_ENDPOINT", "http://localhost:3030/BIM_Knowledge_Base/query")
# Define o caminho para a pasta onde o modelo de NLU treinado está salvo.
NLU_MODEL_PATH = "./nlu_model"
# URI base usada no nosso grafo RDF. Deve ser a mesma usada no setup.py.
BASE_URI = "http://exemplo.org/bim#"

# Dicionário "cérebro" do chatbot. Mapeia palavras-chave da linguagem natural do usuário
# para as relações técnicas correspondentes no grafo. É a chave para a flexibilidade do NLU.
RELATIONSHIP_KEYWORD_MAP = {
    # Relação Técnica: [Lista de palavras-chave únicas e fortes que o usuário pode dizer]
    'isContainedIn': ['onde', 'localização'],
    'hasMaterial': ['material', 'composição'],
    'aggregates': ['contém', 'agrega', 'partes'],
    'isOfType': ['tipo'], # 'tipo' é usado para a relação mais específica (instância de um tipo).
    'type': ['classe'] # 'classe' é usado para a relação mais genérica (instância de uma classe).
}

# Dicionário para traduzir relações técnicas em frases legíveis para as respostas do chatbot,
# especificamente para relações de entrada (inversas).
INVERSE_PROPERTY_MAP = {
    "inst:isContainedIn": "contêm o(a)",
    "inst:hasMaterial": "têm como material",
    "inst:aggregates": "são parte de",
    "inst:isOfType": "são do tipo",
    "rdf:type": "são instâncias da classe"
}

# --- Carregamento do Modelo NLU ---
nlp = None # Inicializa a variável do modelo como nula.
try:
    # Tenta carregar o modelo de NLU treinado pelo setup.py.
    nlp = spacy.load(NLU_MODEL_PATH)
    print("-> Modelo de NLU carregado com sucesso.")
except IOError:
    # Se o modelo não for encontrado, exibe um alerta.
    print(f"-> ALERTA: Modelo de NLU não encontrado. Execute 'python setup.py' primeiro.")

# --- Funções de Lógica do Chatbot ---

# Identifica a intenção principal da frase do usuário (saudação, pergunta, etc.).
def get_intent(text):
    if not nlp: return "error" # Retorna erro se o modelo não foi carregado.
    doc = nlp(text) # Processa o texto com o modelo spaCy.
    # Retorna a categoria com a maior pontuação de confiança.
    return max(doc.cats, key=doc.cats.get)

# Extrai o nome do objeto BIM de interesse da frase do usuário.
def extract_bim_object(text):
    # Usa Regex para encontrar padrões como "do 'objeto'" ou "para o objeto 'objeto'".
    # Esta é a busca prioritária por ser mais explícita.
    explicit_match = re.search(r"(?:para o objeto|do|da|de|para)\s+('([^']*)'|\"([^\"]*)\")", text, re.IGNORECASE)
    if explicit_match:
        # Retorna o conteúdo encontrado dentro das aspas.
        return explicit_match.group(2) or explicit_match.group(3)

    # Se o padrão explícito falhar, usa um fallback que pega a primeira ocorrência entre aspas.
    fallback_match = re.search(r"'([^']*)'|\"([^\"]*)\"", text)
    if fallback_match:
        return fallback_match.group(1) or fallback_match.group(2)
    return None # Retorna None se nenhum objeto for encontrado.

# Extrai a relação (propriedade) que o usuário deseja consultar.
def extract_bim_property(text):
    # Primeiro, verifica se a pergunta foi gerada pelo "Construtor de Consultas".
    match = re.search(r"relação '([^']*)'", text, re.IGNORECASE)
    if match:
        return match.group(1)

    # Se não, usa a lógica de NLU flexível com palavras-chave.
    text_lower = text.lower()
    user_words = set(text_lower.split())

    # Define a ordem de verificação para evitar ambiguidades (ex: 'tipo' vs 'classe').
    relations_in_order = ['isOfType', 'type', 'isContainedIn', 'hasMaterial', 'aggregates']

    for technical_relation in relations_in_order:
        keywords = RELATIONSHIP_KEYWORD_MAP.get(technical_relation, [])
        # Se QUALQUER uma das palavras-chave da relação estiver na pergunta, retorna a relação técnica.
        if any(word in user_words for word in keywords):
            return technical_relation
            
    # Se nenhuma palavra-chave for encontrada, assume que a intenção é pedir o nome do objeto.
    return "label"

# Executa a consulta SPARQL no Fuseki e formata a resposta para o usuário.
def query_bim_property(object_name, predicate_label):
    if not object_name:
        return "Não consegui identificar sobre qual elemento você está perguntando."

    # Constrói o predicado SPARQL completo (ex: 'inst:hasMaterial') a partir do label extraído.
    if predicate_label == 'type':
        predicate = 'rdf:type'
    elif predicate_label == 'label':
        predicate = 'rdfs:label'
    else:
        predicate = f'inst:{predicate_label}'

    sparql = SPARQLWrapper(FUSEKI_ENDPOINT)
    sparql.setReturnFormat(JSON)

    try:
        # --- ETAPA 1: Busca por TODAS as relações de SAÍDA ---
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
            # Formata uma resposta clara indicando que é uma relação de saída e lista todos os resultados.
            return (f"✅ Relação de Saída ({count} resultado(s)): A propriedade '{predicate_label}' para '{object_name}' é: "
                    f"{', '.join(f"'{v}'" for v in values)}.")

        # --- ETAPA 2: Se não houver saída, busca por TODAS as relações de ENTRADA ---
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
            # Formata uma resposta clara indicando que é uma relação de entrada e lista todos os objetos relacionados.
            return (f"➡️ Relação de Entrada ({count} resultado(s)): Os seguintes objetos {inverse_relation_phrase} '{object_name}': "
                    f"{', '.join(f"'{s}'" for s in subjects)}.")

    except Exception as e:
        return f"Erro na consulta SPARQL: {e}"

    # --- ETAPA 3: Se ambas as buscas falharem ---
    return f"❌ Desculpe, não encontrei a propriedade '{predicate_label}' para o objeto '{object_name}', nem relações de entrada ou saída correspondentes."

# --- Endpoints da Aplicação Web ---

# Rota principal que renderiza a página HTML.
@app.route('/')
def index():
    return render_template('index.html')

# Rota que recebe as mensagens do chatbot via POST.
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
        # Extrai o objeto e a propriedade da mensagem e chama a função de consulta.
        bim_object = extract_bim_object(user_message)
        bim_property = extract_bim_property(user_message)
        response_text = query_bim_property(bim_object, bim_property)
    elif intent == "grafo_completo":
        response_text = "OK. Gerando o grafo completo da ontologia..."
        action = "full_graph"
    # Retorna a resposta em formato JSON para o frontend.
    return jsonify({"response": response_text, "object": bim_object, "property": bim_property, "action": action})

# Rota que fornece os dados para a visualização do grafo de um objeto específico.
@app.route('/graph-data')
def get_graph_data():
    object_name = request.args.get('object_name')
    if not object_name:
        return jsonify({"nodes": [], "edges": []})

    sparql = SPARQLWrapper(FUSEKI_ENDPOINT)
    sparql.setReturnFormat(JSON)

    # Consulta que busca todas as relações (de entrada e saída) para o objeto de interesse.
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

        # --- LÓGICA DE COLORAÇÃO PARA O GRAFO ---
        central_node_color = "#a3e635"  # Verde para o nó principal.
        related_node_color = "#93c5fd"  # Azul para os nós relacionados.
        
        for res in results.get("results", {}).get("bindings", []):
            s_uri = res['s']['value']
            s_label = res['s_label']['value']
            o_uri = res['o']['value']
            o_label = res.get('o_label', {}).get('value', o_uri.split('#')[-1])

            # Adiciona o nó de origem (subject) se ele ainda não estiver no grafo.
            if s_uri not in node_ids:
                is_central = s_label == object_name
                color = central_node_color if is_central else related_node_color
                size = 25 if is_central else 15
                nodes.append({"id": s_uri, "label": s_label, "color": color, "size": size})
                node_ids.add(s_uri)

            # Adiciona o nó de destino (object) se ele ainda não estiver no grafo.
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

# Rota que fornece os dados para a visualização do grafo completo (com limite).
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

# Rota que fornece um resumo da ontologia para popular o "Construtor de Consultas".
@app.route('/ontology-summary')
def get_ontology_summary():
    sparql = SPARQLWrapper(FUSEKI_ENDPOINT)
    sparql.setReturnFormat(JSON)

    # Consulta para buscar todos os tipos de objetos e exemplos de instâncias.
    query_types = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX inst: <{BASE_URI}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?type_label (GROUP_CONCAT(DISTINCT ?example_label; SEPARATOR=", ") AS ?examples)
        WHERE {{
            ?s a ?type .
            ?s rdfs:label ?example_label .
            ?type rdfs:label ?type_label .
            FILTER(STRSTARTS(STR(?type), STR(inst:)))
        }} GROUP BY ?type_label ORDER BY ?type_label
    """

    # Consulta para buscar dinamicamente todos os predicados (relações) únicos do grafo.
    query_relations = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX inst: <{BASE_URI}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT DISTINCT ?p_label WHERE {{
            ?s ?p ?o .
            FILTER(isIRI(?s) && isIRI(?p) && isIRI(?o))
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
        
        relations = [res['p_label']['value'] for res in relations_results["results"]["bindings"]]
        
        # Garante que a relação 'type' (rdf:type) esteja sempre na lista para o construtor.
        if 'type' not in relations:
            relations.insert(0, 'type')
        
        return jsonify({"types": types, "relations": relations})

    except Exception as e:
        print(f"Erro ao buscar resumo da ontologia: {e}")
        return jsonify({"error": str(e)}), 500

# --- BLOCO DE EXECUÇÃO PRINCIPAL ---
# Só é executado quando o script é chamado diretamente (ex: 'python app.py').
if __name__ == '__main__':
    # Verifica se o modelo de NLU existe antes de iniciar o servidor.
    if not os.path.exists(NLU_MODEL_PATH):
        print("!!! ATENÇÃO: Modelo de NLU não encontrado.")
        print("!!! Execute 'python setup.py' para criar os modelos e dados necessários.")
    else:
        # Inicia o servidor Flask, acessível na rede local.
        app.run(host='0.0.0.0', port=5000, debug=False)
