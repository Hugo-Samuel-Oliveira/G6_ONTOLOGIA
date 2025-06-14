# Importações de bibliotecas essenciais para o script
import ifcopenshell  # Para ler e interpretar arquivos .ifc
from rdflib import Graph, Namespace, Literal  # Para criar e manipular o grafo de conhecimento (RDF)
from rdflib.namespace import RDF, RDFS  # Vocabulários RDF e RDFS padrão (para 'type', 'label', etc.)
import spacy  # Para treinar o modelo de Processamento de Linguagem Natural (NLU)
from spacy.training.example import Example  # Classe auxiliar para o treinamento do spaCy
import random  # Usado para embaralhar os dados de treino
import os  # Para interagir com o sistema de arquivos (verificar/criar pastas)
import requests  # Para fazer requisições HTTP para o servidor Fuseki

# --- FUNÇÃO DE CONVERSÃO IFC PARA RDF ---
# Responsável por ler o arquivo .ifc e traduzir sua estrutura para um grafo RDF (em formato Turtle).
def run_ifc_conversion():
    """
    Abre um arquivo IFC, extrai seus elementos e relações,
    e os converte em um grafo RDF usando a biblioteca rdflib.
    """
    # --- Configurações Iniciais ---
    IFC_FILE_PATH = 'Building-Architecture.ifc'  # Caminho para o arquivo BIM a ser processado.
    BASE_URI = "http://exemplo.org/bim#"  # URI base para criar os identificadores únicos no nosso grafo.
    inst = Namespace(BASE_URI)  # Cria um namespace customizado para nossas entidades (ex: inst:IfcWall).
    g = Graph()  # Inicializa um grafo RDF vazio.
    # Associa os prefixos 'inst', 'rdfs', e 'rdf' à URI correspondente para deixar o arquivo .ttl mais legível.
    g.bind("inst", inst); g.bind("rdfs", RDFS); g.bind("rdf", RDF)
    
    # Tenta abrir o arquivo IFC e lida com possíveis erros.
    try:
        ifc_file = ifcopenshell.open(IFC_FILE_PATH)
    except Exception as e:
        print(f"ERRO: Não foi possível abrir o arquivo IFC '{IFC_FILE_PATH}'. {e}")
        return None
    
    print(f"Processando {ifc_file.schema} de {IFC_FILE_PATH}...")
    # Seleciona todas as definições de objetos (paredes, lajes, espaços, etc.) do arquivo.
    all_elements = ifc_file.by_type('IfcObjectDefinition')
    
    # Primeiro loop: Itera sobre todos os elementos para extrair informações básicas.
    for element in all_elements:
        element_uri = inst[element.GlobalId]  # Cria uma URI única para o elemento usando seu GlobalId.
        # Adiciona o nome do elemento como um 'label' (rótulo legível).
        if getattr(element, 'Name', None): g.add((element_uri, RDFS.label, Literal(element.Name)))
        # Adiciona a classe do elemento (ex: 'IfcWall') e também um label para a própria classe.
        element_class_uri = inst[element.is_a()]; g.add((element_uri, RDF.type, element_class_uri)); g.add((element_class_uri, RDFS.label, Literal(element.is_a())))
        
    # Segundo loop: Itera sobre todas as RELAÇÕES para conectar os elementos.
    for rel in ifc_file.by_type('IfcRelationship'):
        # Se for uma relação de material...
        if rel.is_a('IfcRelAssociatesMaterial') and hasattr(rel, 'RelatedObjects'):
            for obj in rel.RelatedObjects:
                if getattr(obj, 'Name', None):
                    mat_select = rel.RelatingMaterial
                    if mat_select and mat_select.is_a('IfcMaterial'):
                        mat_uri = inst[f"Mat_{mat_select.Name.replace(' ', '_')}"]
                        g.add((mat_uri, RDFS.label, Literal(mat_select.Name)))
                        # Adiciona a tripla: (objeto, temMaterial, material)
                        g.add((inst[obj.GlobalId], inst.hasMaterial, mat_uri))
        # Se for uma relação de contenção espacial (um objeto dentro de outro)...
        elif rel.is_a('IfcRelContainedInSpatialStructure') and hasattr(rel, 'RelatedElements'):
            if getattr(rel.RelatingStructure, 'Name', None):
                for element in rel.RelatedElements:
                    # Adiciona a tripla: (elemento, estaContidoEm, estrutura)
                    if getattr(element, 'Name', None): g.add((inst[element.GlobalId], inst.isContainedIn, inst[rel.RelatingStructure.GlobalId]))
        # Se for uma relação de tipo (uma instância de um tipo específico)...
        elif rel.is_a('IfcRelDefinesByType') and hasattr(rel, 'RelatedObjects'):
            if getattr(rel.RelatingType, 'Name', None):
                type_uri = inst[rel.RelatingType.GlobalId]
                g.add((type_uri, RDFS.label, Literal(rel.RelatingType.Name)))
                for element in rel.RelatedObjects:
                    # Adiciona a tripla: (elemento, ehDoTipo, tipo)
                    if getattr(element, 'Name', None): g.add((inst[element.GlobalId], inst.isOfType, type_uri))
        # Se for uma relação de agregação (um objeto composto por partes)...
        elif rel.is_a('IfcRelAggregates') and hasattr(rel, 'RelatedObjects'):
            if getattr(rel.RelatingObject, 'Name', None):
                for part in rel.RelatedObjects:
                    # Adiciona a tripla: (objetoPai, agrega, objetoParte)
                    if getattr(part, 'Name', None): g.add((inst[rel.RelatingObject.GlobalId], inst.aggregates, inst[part.GlobalId]))
    
    print(f"-> Conversão concluída. {len(g)} triplos gerados.")

    # Bloco removido na refatoração para não salvar mais o arquivo .ttl
    # Anteriormente, este código salvava o grafo em 'static/modelo_convertido.ttl'

    return g

# --- FUNÇÃO DE TREINAMENTO DO NLU ---
# Responsável por treinar um modelo simples de spaCy para classificar a intenção do usuário.
def run_nlu_training():
    """
    Cria e treina um modelo de classificação de texto (NLU) com base
    em exemplos de frases e suas intenções correspondentes.
    """
    NLU_MODEL_PATH = "./nlu_model"  # Pasta onde o modelo treinado será salvo.
    # Dados de treinamento: pares de (frase de exemplo, dicionário de intenções).
    TRAIN_DATA = [
        ("oi", {"cats": {"saudacao": 1.0, "despedida": 0.0, "perguntar_propriedade": 0.0, "grafo_completo": 0.0}}),
        ("olá", {"cats": {"saudacao": 1.0, "despedida": 0.0, "perguntar_propriedade": 0.0, "grafo_completo": 0.0}}),
        ("tchau", {"cats": {"saudacao": 0.0, "despedida": 1.0, "perguntar_propriedade": 0.0, "grafo_completo": 0.0}}),
        ("qual o material do 'floor'?", {"cats": {"saudacao": 0.0, "despedida": 0.0, "perguntar_propriedade": 1.0, "grafo_completo": 0.0}}),
        ("onde está o 'floor'?", {"cats": {"saudacao": 0.0, "despedida": 0.0, "perguntar_propriedade": 1.0, "grafo_completo": 0.0}}),
        ("qual o tipo do 'floor'?", {"cats": {"saudacao": 0.0, "despedida": 0.0, "perguntar_propriedade": 1.0, "grafo_completo": 0.0}}),
        ("mostre o grafo inteiro", {"cats": {"saudacao": 0.0, "despedida": 0.0, "perguntar_propriedade": 0.0, "grafo_completo": 1.0}}),
        ("gere a ontologia completa", {"cats": {"saudacao": 0.0, "despedida": 0.0, "perguntar_propriedade": 0.0, "grafo_completo": 1.0}}),
    ]
    nlp_train = spacy.blank("pt")  # Cria um modelo de linguagem vazio para o português.
    textcat = nlp_train.add_pipe("textcat")  # Adiciona um componente de classificação de texto (textcat).
    # Adiciona as possíveis categorias (labels) de intenção ao classificador.
    textcat.add_label("saudacao"); textcat.add_label("despedida"); textcat.add_label("perguntar_propriedade"); textcat.add_label("grafo_completo")
    nlp_train.initialize()  # Inicializa o treinamento.
    # Itera várias vezes sobre os dados de treino para que o modelo aprenda.
    for i in range(15):
        random.shuffle(TRAIN_DATA)  # Embaralha os dados a cada iteração para evitar viés.
        losses = {}
        # Atualiza o modelo com cada exemplo de treino.
        for text, annotations in TRAIN_DATA:
            doc = nlp_train.make_doc(text)
            example = Example.from_dict(doc, annotations)
            nlp_train.update([example], losses=losses)
    nlp_train.to_disk(NLU_MODEL_PATH)  # Salva o modelo treinado na pasta especificada.
    print(f"-> Modelo de NLU treinado e salvo em '{NLU_MODEL_PATH}'.")

# --- FUNÇÃO DE UPLOAD PARA O FUSEKI ---
# Responsável por limpar e carregar o novo grafo no servidor de triplestore.
def upload_to_fuseki(graph):
    """
    Conecta-se ao endpoint do Apache Jena Fuseki, apaga os dados antigos
    e envia o novo grafo RDF gerado.
    """
    # Endpoint do protocolo Graph Store (GSP), que permite a manipulação de grafos via HTTP.
    FUSEKI_GSP_ENDPOINT = "http://localhost:3030/BIM_Knowledge_Base/data"
    print("-> Limpando o grafo no Fuseki...")
    try:
        # Envia uma requisição HTTP DELETE para apagar o grafo padrão.
        requests.delete(FUSEKI_GSP_ENDPOINT, params={'default': ''}).raise_for_status()
        print("   Grafo limpo com sucesso.")
    except requests.exceptions.RequestException as e:
        print(f"ERRO: Não foi possível conectar ao Fuseki para limpar o grafo. Verifique se ele está rodando. Erro: {e}")
        return False
    
    print(f"-> Carregando {len(graph)} triplos no Fuseki...")
    try:
        # Envia uma requisição HTTP POST com o grafo serializado em formato Turtle.
        requests.post(
            FUSEKI_GSP_ENDPOINT, params={'default': ''}, data=graph.serialize(format='turtle'),
            headers={'Content-Type': 'text/turtle'}
        ).raise_for_status()
        print("   Novos dados carregados com sucesso.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"ERRO: Falha na comunicação durante o upload para o Fuseki. Erro: {e}")
        return False

# --- BLOCO DE EXECUÇÃO PRINCIPAL ---
# Este bloco só é executado quando o script é chamado diretamente (ex: 'python setup.py').
if __name__ == "__main__":
    print("Iniciando configuração completa...")
    # 1. Converte o arquivo IFC para um grafo RDF.
    rdf_graph = run_ifc_conversion()
    # 2. Se a conversão e o upload para o Fuseki forem bem-sucedidos...
    if rdf_graph and upload_to_fuseki(rdf_graph):
        # 3. ...então treina o modelo de NLU.
        run_nlu_training()
        print("\nConfiguração concluída. Agora você pode executar 'python app.py' para iniciar o servidor.")
    else:
        print("\nConfiguração falhou.")
