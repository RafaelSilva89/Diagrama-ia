import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma

# ============================================================
# 1. Carregar variaveis de ambiente
# ============================================================
_IA_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE_DIR = os.path.dirname(_IA_DIR)
load_dotenv(os.path.join(_BASE_DIR, '.env'))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
_CHROMA_DIR = os.path.join(_IA_DIR, "chroma_db")

# ============================================================
# 2. Conectar ao banco vetorial existente
# ============================================================
embedding_function = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=OPENAI_API_KEY,
)

vectorstore = Chroma(
    collection_name="multi_modal_rag",
    embedding_function=embedding_function,
    persist_directory=_CHROMA_DIR,
)

retriever = vectorstore.as_retriever()

# ============================================================
# 3. Guardrails de filtragem de conteudo
# ============================================================

PALAVRAS_PROIBIDAS = [
    "inferioridade", "superioridade racial", "discurso de odio",
    "preguicosos", "preguicosas", "terrorismo", "supremacia",
    "exterminacao", "genocidio", "armas biologicas", "armas quimicas",
    "hack senha", "invadir sistema", "roubar dados",
]

PROMPT_GUARDRAIL = """Voce e um classificador de seguranca. Analise a solicitacao abaixo e determine:
1. Se ela e relacionada a analise de diagramas de software, arquitetura de sistemas, UML, design patterns, ou engenharia de software.
2. Se ela contem discurso de odio, conteudo ofensivo, vieses culturais/religiosos/genero, ou qualquer conteudo inadequado.

Solicitacao: {pergunta}

Responda APENAS com um JSON no formato:
{{"valida": true/false, "motivo": "explicacao breve"}}

Regras:
- "valida": true SOMENTE se a solicitacao for sobre analise de diagramas/software E nao contiver conteudo inadequado
- "valida": false se for sobre qualquer outro tema ou contiver conteudo sensivel
- Seja rigoroso: apenas temas de engenharia de software sao permitidos"""


def validar_consulta(pergunta: str) -> tuple:
    """Guardrail: valida se a consulta e sobre analise de diagrama de software.
    Retorna (True, "") se valida, (False, "motivo") se invalida.
    """
    # Filtro rapido por palavras proibidas
    pergunta_lower = pergunta.lower()
    for palavra in PALAVRAS_PROIBIDAS:
        if palavra in pergunta_lower:
            return (False, f"Conteudo inadequado detectado. Este sistema responde apenas sobre analise de diagramas de software.")

    # Validacao por LLM
    try:
        llm_guard = ChatOpenAI(model="gpt-4o-mini", openai_api_key=OPENAI_API_KEY, temperature=0)
        prompt = ChatPromptTemplate.from_messages([
            ("human", PROMPT_GUARDRAIL),
        ])
        chain = prompt | llm_guard | StrOutputParser()
        resultado = chain.invoke({"pergunta": pergunta})

        import json
        parsed = json.loads(resultado)
        if not parsed.get("valida", False):
            motivo = parsed.get("motivo", "Consulta fora do escopo de analise de diagramas de software.")
            return (False, motivo)
        return (True, "")
    except Exception:
        # Em caso de erro no guardrail, permite a consulta (fail-open para nao bloquear funcionalidade)
        return (True, "")


# ============================================================
# 4. Funcoes auxiliares do pipeline RAG
# ============================================================
def parse_docs(docs):
    """Separar imagens de textos usando o metadado 'tipo', mantendo metadados"""
    images = []
    texts = []
    for doc in docs:
        tipo = doc.metadata.get("tipo", "texto")
        original = doc.metadata.get("original_content", doc.page_content)
        if tipo == "imagem":
            images.append({"content": original, "metadata": doc.metadata})
        else:
            texts.append({"content": original, "metadata": doc.metadata})
    return {"images": images, "texts": texts}


def build_prompt(kwargs):
    docs_by_type = kwargs["context"]
    user_question = kwargs["question"]

    context_text = "\n\n".join([t["content"] for t in docs_by_type["texts"]])

    prompt_template = f"""
    Voce e um especialista em engenharia de software e analise de diagramas.
    Responda a pergunta baseando-se apenas no seguinte contexto, que pode incluir texto, tabelas e as imagens abaixo.
    Responda de forma concisa em no maximo 2-3 frases curtas.
    Identifique o conceito tecnico central e sugira a acao corretiva principal.
    Nao inclua definicoes academicas extensas.
    Se o contexto nao contiver informacao suficiente, diga claramente.

    Contexto: {context_text}
    Pergunta: {user_question}
    """

    prompt_content = [{"type": "text", "text": prompt_template}]

    for image in docs_by_type["images"]:
        prompt_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image['content']}"},
            }
        )

    return ChatPromptTemplate.from_messages(
        [HumanMessage(content=prompt_content)]
    )


# ============================================================
# 5. Pipeline RAG
# ============================================================
llm = ChatOpenAI(
    model="gpt-4o-mini",
    openai_api_key=OPENAI_API_KEY,
)

chain_with_sources = (
    {
        "context": retriever | RunnableLambda(parse_docs),
        "question": RunnablePassthrough(),
    }
    | RunnablePassthrough.assign(
        response=RunnableLambda(build_prompt) | llm | StrOutputParser()
    )
)


def _extrair_fontes(context: dict) -> list:
    """Extrai fontes unicas do contexto RAG."""
    sources_seen = set()
    sources = []
    all_items = context.get("texts", []) + context.get("images", [])
    for item in all_items:
        meta = item.get("metadata", {})
        filename = meta.get("filename", "desconhecido")
        page = meta.get("page_number", "")
        tipo = meta.get("tipo", "texto")
        key = (filename, str(page))
        if key not in sources_seen:
            sources_seen.add(key)
            sources.append({"filename": filename, "page_number": str(page), "tipo": tipo})
    return sources


def consultar_rag(pergunta: str) -> dict:
    """Consulta o banco vetorial e retorna resposta enriquecida com fontes.

    Args:
        pergunta: Texto da consulta sobre analise de diagrama.

    Returns:
        dict com:
            - "resposta": str com a resposta enriquecida
            - "fontes": list de dicts com {"filename", "page_number", "tipo"}
            - "valida": bool indicando se passou nos guardrails
            - "motivo_bloqueio": str com motivo caso bloqueada
    """
    # Aplicar guardrails
    valida, motivo = validar_consulta(pergunta)
    if not valida:
        return {
            "resposta": "",
            "fontes": [],
            "valida": False,
            "motivo_bloqueio": motivo,
        }

    try:
        response = chain_with_sources.invoke(pergunta)
        fontes = _extrair_fontes(response.get("context", {}))
        return {
            "resposta": response.get("response", ""),
            "fontes": fontes,
            "valida": True,
            "motivo_bloqueio": "",
        }
    except Exception as e:
        return {
            "resposta": "",
            "fontes": [],
            "valida": True,
            "motivo_bloqueio": f"Erro ao consultar RAG: {str(e)}",
        }


# ============================================================
# 6. Execucao direta (opcional, para testes)
# ============================================================
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        pergunta = " ".join(sys.argv[1:])
    else:
        pergunta = input("Digite sua pergunta: ")

    print(f"\nPergunta: {pergunta}\n")
    print("Buscando resposta...\n")

    resultado = consultar_rag(pergunta)

    if not resultado["valida"]:
        print(f"Consulta bloqueada: {resultado['motivo_bloqueio']}")
    else:
        print("Resposta:", resultado["resposta"])

        if resultado["fontes"]:
            print("\n" + "=" * 50)
            print("Fontes:")
            print("=" * 50)
            for s in resultado["fontes"]:
                page_info = f", Pagina: {s['page_number']}" if s["page_number"] else ""
                print(f"  Documento: {s['filename']}{page_info} ({s['tipo']})")
