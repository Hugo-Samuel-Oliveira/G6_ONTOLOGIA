import ifcopenshell
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, RDFS

# --- Configuração ---
# Altere este caminho para apontar para o seu arquivo .ifc
IFC_FILE_PATH = './Building-Architecture.ifc' 
OUTPUT_TTL_PATH = 'modelo_convertido.ttl'
BASE_URI = "http://exemplo.org/bim#"

# --- Namespaces ---
IFCOWL = Namespace("http://ifcowl.openbimstandards.org/ifc2x3/ifc#")
inst = Namespace(BASE_URI)

# --- Inicialização ---
g = Graph()
# Binds para um output mais limpo
g.bind("ifc", IFCOWL)
g.bind("inst", inst)
g.bind("rdfs", RDFS)

try:
    ifc_file = ifcopenshell.open(IFC_FILE_PATH)
    print(f"Processando o arquivo IFC: {IFC_FILE_PATH}")
except Exception as e:
    print(f"Erro ao abrir o arquivo IFC: {e}")
    exit()


# --- Processando Paredes e seus Materiais ---
walls = ifc_file.by_type('IfcWall')
print(f"\nEncontradas {len(walls)} paredes. Processando...")

for wall in walls:
    # Cria uma URI para a parede usando seu GlobalId, que é único
    wall_uri = inst[wall.GlobalId]
    g.add((wall_uri, RDF.type, IFCOWL.IfcWall))
    g.add((wall_uri, RDFS.label, Literal(wall.Name))) # Adiciona o nome como label
    
    # Navega pelas associações para encontrar o material
    for rel in getattr(wall, 'HasAssociations', []):
        if rel.is_a('IfcRelAssociatesMaterial'):
            material_select = rel.RelatingMaterial
            # A lógica pode variar dependendo se o material é uma camada, lista, etc.
            if hasattr(material_select, 'ForLayerSet'):
                material_layer_set = material_select.ForLayerSet
                for material_layer in material_layer_set.MaterialLayers:
                    material = material_layer.Material
                    if material:
                        material_uri = inst[f"Material_{material.Name.replace(' ', '_')}"]
                        g.add((material_uri, RDF.type, IFCOWL.IfcMaterial))
                        g.add((material_uri, RDFS.label, Literal(material.Name)))
                        # Adiciona a nossa propriedade customizada 'hasMaterial'
                        g.add((wall_uri, inst.hasMaterial, material_uri))
                        print(f"  -> Parede '{wall.Name}' associada ao Material '{material.Name}'")
            # Caso simples de associação direta
            elif material_select.is_a('IfcMaterial'):
                 material = material_select
                 material_uri = inst[f"Material_{material.Name.replace(' ', '_')}"]
                 g.add((material_uri, RDF.type, IFCOWL.IfcMaterial))
                 g.add((material_uri, RDFS.label, Literal(material.Name)))
                 g.add((wall_uri, inst.hasMaterial, material_uri))
                 print(f"  -> Parede '{wall.Name}' associada ao Material '{material.Name}'")


# --- Processando Lajes e seus Materiais ---
slabs = ifc_file.by_type('IfcSlab')
print(f"\nEncontradas {len(slabs)} lajes. Processando...")
for slab in slabs:
    slab_uri = inst[slab.GlobalId]
    g.add((slab_uri, RDF.type, IFCOWL.IfcSlab))
    g.add((slab_uri, RDFS.label, Literal(slab.Name)))

    for rel in getattr(slab, 'HasAssociations', []):
        if rel.is_a('IfcRelAssociatesMaterial'):
            material = rel.RelatingMaterial
            if material and material.is_a('IfcMaterial'):
                material_uri = inst[f"Material_{material.Name.replace(' ', '_')}"]
                g.add((material_uri, RDF.type, IFCOWL.IfcMaterial))
                g.add((material_uri, RDFS.label, Literal(material.Name)))
                g.add((slab_uri, inst.hasMaterial, material_uri))
                print(f"  -> Laje '{slab.Name}' associada ao Material '{material.Name}'")


# --- Serialização para o arquivo de saída ---
g.serialize(destination=OUTPUT_TTL_PATH, format='turtle')

print(f"\nConversão concluída! Arquivo salvo em: {OUTPUT_TTL_PATH}")

