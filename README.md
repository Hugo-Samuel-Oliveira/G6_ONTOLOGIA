# G6_ONTOLOGIA
# Assistente Virtual Semântico para Projetos BIM

## 1. Visão Geral

Este projeto é uma aplicação web que funciona como um **assistente virtual (chatbot)** para consulta de modelos de construção no formato **IFC (Industry Foundation Classes)**. O sistema permite que um utilizador faça perguntas em **linguagem natural** sobre os elementos de um projeto BIM e receba **respostas precisas**, obtidas através de **consultas semânticas a uma base de conhecimento ontológica**.

O objetivo principal é **demonstrar a aplicação prática da Web Semântica e de ontologias** para extrair e explorar o conhecimento inerente aos modelos BIM, que muitas vezes permanece inacessível em softwares tradicionais.

### A aplicação inclui uma interface gráfica com:

- Um **chatbot** para interação por texto.
- Uma **visualização de grafo interativa** que exibe as relações do objeto consultado.
- Um **construtor de consultas** para ajudar os utilizadores a descobrir e formular perguntas sobre a ontologia.

---

## 2. Tecnologias Utilizadas

A aplicação foi construída com uma pilha de tecnologias de código aberto, focada em simplicidade e robustez:

### Backend

- **Python 3**: Linguagem principal da aplicação.
- **Flask**: Micro-framework web utilizado para criar a API que serve o frontend e processa as requisições do chatbot.

### Processamento de Linguagem Natural (NLU)

- **spaCy**: Biblioteca de NLP usada para treinar um modelo que reconhece as intenções do utilizador (ex: `"perguntar propriedade"`, `"mostrar grafo completo"`).

### Base de Conhecimento (Web Semântica)

- **Apache Jena Fuseki**: Servidor de grafos (Triplestore) que armazena a ontologia e os dados do projeto, expondo um endpoint para consultas.
- **SPARQL**: Linguagem de consulta padrão para bases de dados RDF.

### Ontologia (ifcOWL)

- Estrutura de conhecimento baseada no padrão **ifcOWL**, com **predicados customizados** para representar relações do BIM.

### Manipulação de Dados IFC e RDF

- **IfcOpenShell**: Biblioteca Python para ler e extrair dados de arquivos `.ifc`.
- **rdflib**: Biblioteca para criar, manipular e serializar dados no formato RDF.

### Frontend

- **HTML5 / CSS3 / JavaScript**: Estrutura base da interface do utilizador.
- **Tailwind CSS**: Framework CSS para uma estilização rápida e moderna.
- **Vis.js**: Biblioteca JavaScript para visualização de redes e grafos dinâmicos e interativos.

---

## 3. Guia de Instalação e Execução

### 3.1. Pré-requisitos

- Python 3.8 ou superior  
- Java Development Kit (JDK) 8 ou superior  
- Git para clonar o repositório  

### 3.2. Estrutura do Projeto

Certifique-se de que a sua estrutura de pastas corresponde à seguinte:

```
/seu-projeto/
|-- templates/
|   |-- index.html
|-- app.py
|-- setup.py
|-- requirements.txt
|-- Building-Architecture.ifc
|-- .gitignore
|-- venv/
```

### 3.3. Passos de Configuração

**1. Clone o Repositório:**
```bash
git clone <URL_DO_SEU_REPOSITORIO>
cd <NOME_DA_PASTA_DO_PROJETO>
```

**2. Crie e Ative o Ambiente Virtual:**
```bash
# Criar o ambiente virtual
python -m venv venv

# Ativar no Windows (PowerShell/CMD)
.\venv\Scripts\activate

# Ativar no macOS/Linux
source venv/bin/activate
```

**3. Instale as Dependências:**
```bash
pip install -r requirements.txt
python -m spacy download pt_core_news_lg
```

**4. Configure e Inicie o Apache Jena Fuseki:**

- Baixe e descompacte o Apache Jena Fuseki.
- Inicie o servidor:
  - Windows: `fuseki-server.bat`
  - macOS/Linux: `./fuseki-server`
- Acesse: [http://localhost:3030](http://localhost:3030)
- Clique em “**new dataset**”
  - Nome do dataset: `BIM_Knowledge_Base`
  - Tipo: **In-memory**
  - Clique em “Create dataset”

---

### 3.4. Roteiro de Execução

Com o Fuseki a rodar, siga estes dois comandos (com o ambiente virtual ativado):

**1. Execute o Script de Setup (Apenas uma vez):**
```bash
python setup.py
```
> Aguarde até a mensagem **"Configuração concluída"**.

**2. Inicie o Servidor Flask:**
```bash
python app.py
```

> O terminal deve indicar que o servidor está rodando.

**3. Acesse a Aplicação:**

Abra o navegador em: [http://localhost:5000](http://localhost:5000)

---

## 4. Como Usar

### Chatbot

- Faça perguntas em **linguagem natural** na caixa de texto.
- Use **aspas simples** para indicar o nome exato dos objetos (ex: `'floor'`).

### Construtor de Consultas

- Expanda o painel “Construtor de Consultas”.
- Selecione uma relação e um objeto nos menus.
- Clique em “**Gerar Pergunta**” para criar um comando de exemplo.

### Visualização do Grafo

- O grafo é gerado **automaticamente após uma consulta bem-sucedida**.

- # Reconhecimentos e Direitos Autorais

**@autor:** Hugo Samuel Oliveira, Kellyson Aguiar, Luis Fernando Cuvelo, Paulo Brito  
**@contato:** [Opcional – inserir e-mails se desejarem]  
**@data última versão:** 13/06/2025  
**@versão:** 1.0  
**@outros repositórios:** https://github.com/Hugo-Samuel-Oliveira/G6_ONTOLOGIA

**@Agradecimentos:**  
Universidade Federal do Maranhão (UFMA), Professor Doutor Thales Levi Azevedo Valente, e colegas de curso.

---

## Copyright / License

Este material é resultado de um trabalho acadêmico para a disciplina **INTELIGÊNCIA ARTIFICIAL**, sob a orientação do professor Dr. **THALES LEVI AZEVEDO VALENTE**, semestre letivo **2025.1**, curso **Engenharia da Computação**, na Universidade Federal do Maranhão (UFMA).

Todo o material sob esta licença é software livre: pode ser usado para fins acadêmicos e comerciais sem nenhum custo.  
Não há papelada, nem royalties, nem restrições de "copyleft" do tipo GNU.  

Ele é licenciado sob os termos da **Licença MIT**, conforme descrito abaixo, e, portanto, é compatível com a GPL e também se qualifica como software de código aberto.  
É de domínio público. O espírito desta licença é que você é livre para usar este material para qualquer finalidade, sem nenhum custo.  
O único requisito é que, se você usá-lo, **nos dê crédito**.

---

## Licença MIT (MIT License)

Permissão é concedida, gratuitamente, a qualquer pessoa que obtenha uma cópia deste software e dos arquivos de documentação associados (o "Software"), para lidar no Software sem restrição, incluindo sem limitação os direitos de:

- usar,  
- copiar,  
- modificar,  
- mesclar,  
- publicar,  
- distribuir,  
- sublicenciar e/ou  
- vender cópias do Software,  

e permitir pessoas a quem o Software é fornecido a fazê-lo, **sujeito às seguintes condições**:

> Este aviso de direitos autorais e este aviso de permissão devem ser incluídos em todas as cópias ou partes substanciais do Software.

---

O SOFTWARE É FORNECIDO "COMO ESTÁ", SEM GARANTIA DE QUALQUER TIPO, EXPRESSA OU IMPLÍCITA, INCLUINDO MAS NÃO SE LIMITANDO ÀS GARANTIAS DE COMERCIALIZAÇÃO, ADEQUAÇÃO A UM DETERMINADO FIM E NÃO INFRINGÊNCIA.  
EM NENHUM CASO OS AUTORES OU DETENTORES DE DIREITOS AUTORAIS SERÃO RESPONSÁVEIS POR QUALQUER RECLAMAÇÃO, DANOS OU OUTRA RESPONSABILIDADE, SEJA EM AÇÃO DE CONTRATO, TORT OU OUTRA FORMA, DECORRENTE DE, FORA DE OU EM CONEXÃO COM O SOFTWARE OU O USO OU OUTRAS NEGOCIAÇÕES NO SOFTWARE.

---

🔗 Para mais informações sobre a Licença MIT: [https://opensource.org/licenses/MIT](https://opensource.org/licenses/MIT)

