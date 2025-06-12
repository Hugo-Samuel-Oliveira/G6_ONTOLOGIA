import ifcopenshell
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, RDFS
import spacy
from spacy.training.example import Example
import random
import os
import requests

def run_ifc_conversion():
    # --- Configuração ---
    IFC_FILE_PATH = 'Building-Architecture.ifc' 
    BASE_URI = "http://exemplo.org/bim#"
    inst = Namespace(BASE_URI)
    g = Graph()
    g.bind("inst", inst); g.bind("rdfs", RDFS); g.bind("rdf", RDF)
    
    try:
        ifc_file = ifcopenshell.open(IFC_FILE_PATH)
    except Exception as e:
        print(f"ERRO: Não foi possível abrir o arquivo IFC '{IFC_FILE_PATH}'. {e}")
        return None
    
    print(f"Processando {ifc_file.schema} de {IFC_FILE_PATH}...")
    all_elements = ifc_file.by_type('IfcObjectDefinition')
    
    for element in all_elements:
        element_uri = inst[element.GlobalId]
        if getattr(element, 'Name', None): g.add((element_uri, RDFS.label, Literal(element.Name)))
        element_class_uri = inst[element.is_a()]; g.add((element_uri, RDF.type, element_class_uri)); g.add((element_class_uri, RDFS.label, Literal(element.is_a())))
        
    for rel in ifc_file.by_type('IfcRelationship'):
        if rel.is_a('IfcRelAssociatesMaterial') and hasattr(rel, 'RelatedObjects'):
            for obj in rel.RelatedObjects:
                if getattr(obj, 'Name', None):
                    mat_select = rel.RelatingMaterial
                    if mat_select and mat_select.is_a('IfcMaterial'):
                        mat_uri = inst[f"Mat_{mat_select.Name.replace(' ', '_')}"]
                        g.add((mat_uri, RDFS.label, Literal(mat_select.Name)))
                        g.add((inst[obj.GlobalId], inst.hasMaterial, mat_uri))
        elif rel.is_a('IfcRelContainedInSpatialStructure') and hasattr(rel, 'RelatedElements'):
            if getattr(rel.RelatingStructure, 'Name', None):
                for element in rel.RelatedElements:
                    if getattr(element, 'Name', None): g.add((inst[element.GlobalId], inst.isContainedIn, inst[rel.RelatingStructure.GlobalId]))
        elif rel.is_a('IfcRelDefinesByType') and hasattr(rel, 'RelatedObjects'):
            if getattr(rel.RelatingType, 'Name', None):
                type_uri = inst[rel.RelatingType.GlobalId]
                g.add((type_uri, RDFS.label, Literal(rel.RelatingType.Name)))
                for element in rel.RelatedObjects:
                    if getattr(element, 'Name', None): g.add((inst[element.GlobalId], inst.isOfType, type_uri))
        elif rel.is_a('IfcRelAggregates') and hasattr(rel, 'RelatedObjects'):
            if getattr(rel.RelatingObject, 'Name', None):
                for part in rel.RelatedObjects:
                    if getattr(part, 'Name', None): g.add((inst[rel.RelatingObject.GlobalId], inst.aggregates, inst[part.GlobalId]))
    
    print(f"-> Conversão concluída. {len(g)} triplos gerados.")
    return g

def run_nlu_training():
    NLU_MODEL_PATH = "./nlu_model"
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
    nlp_train = spacy.blank("pt"); textcat = nlp_train.add_pipe("textcat")
    textcat.add_label("saudacao"); textcat.add_label("despedida"); textcat.add_label("perguntar_propriedade"); textcat.add_label("grafo_completo")
    nlp_train.initialize()
    for i in range(15): # Aumentado para melhor aprendizado
        random.shuffle(TRAIN_DATA); losses = {}
        for text, annotations in TRAIN_DATA:
            doc = nlp_train.make_doc(text); example = Example.from_dict(doc, annotations)
            nlp_train.update([example], losses=losses)
    nlp_train.to_disk(NLU_MODEL_PATH)
    print(f"-> Modelo de NLU treinado e salvo em '{NLU_MODEL_PATH}'.")

def upload_to_fuseki(graph):
    FUSEKI_GSP_ENDPOINT = "http://localhost:3030/BIM_Knowledge_Base/data"
    print("-> Limpando o grafo no Fuseki...")
    try:
        requests.delete(FUSEKI_GSP_ENDPOINT, params={'default': ''}).raise_for_status()
        print("   Grafo limpo com sucesso.")
    except requests.exceptions.RequestException as e:
        print(f"ERRO: Não foi possível conectar ao Fuseki para limpar o grafo. Verifique se ele está rodando. Erro: {e}")
        return False
    
    print(f"-> Carregando {len(graph)} triplos no Fuseki...")
    try:
        requests.post(
            FUSEKI_GSP_ENDPOINT, params={'default': ''}, data=graph.serialize(format='turtle'),
            headers={'Content-Type': 'text/turtle'}
        ).raise_for_status()
        print("   Novos dados carregados com sucesso.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"ERRO: Falha na comunicação durante o upload para o Fuseki. Erro: {e}")
        return False

if __name__ == "__main__":
    print("Iniciando configuração completa...")
    rdf_graph = run_ifc_conversion()
    if rdf_graph and upload_to_fuseki(rdf_graph):
        run_nlu_training()
        print("\nConfiguração concluída. Agora você pode executar 'python app.py' para iniciar o servidor.")
    else:
        print("\nConfiguração falhou.")
