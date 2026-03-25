import os
import uuid
from dotenv import load_dotenv
from openai import BadRequestError
from unstructured.partition.pdf import partition_pdf
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_chroma import Chroma

# ============================================================
# 1. Carregar variáveis de ambiente
# ============================================================
load_dotenv()

# Configurar Tesseract OCR - apontar para tessdata local com idioma português
tessdata_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tessdata")
os.environ["TESSDATA_PREFIX"] = tessdata_path

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ============================================================
# 2. Extrair elementos dos PDFs
# ============================================================
base_dir = os.path.dirname(os.path.abspath(__file__))
doc_folder = os.path.join(base_dir, "doc")
pdf_files = sorted([f for f in os.listdir(doc_folder) if f.endswith('.pdf')])

all_chunks = []

for pdf_file in pdf_files:
    file_path = os.path.join(doc_folder, pdf_file)
    print(f"Processando: {pdf_file}")

    chunks = partition_pdf(
        filename=file_path,
        infer_table_structure=True,
        strategy="hi_res",
        extract_image_block_types=["Image"],
        extract_image_block_to_payload=True,
        chunking_strategy="by_title",
        max_characters=10000,
        combine_text_under_n_chars=2000,
        new_after_n_chars=6000,
        languages=["por"],
    )

    for chunk in chunks:
        if hasattr(chunk, "metadata"):
            chunk.metadata.filename = pdf_file
            if hasattr(chunk.metadata, "orig_elements") and chunk.metadata.orig_elements:
                for el in chunk.metadata.orig_elements:
                    if hasattr(el, "metadata"):
                        el.metadata.filename = pdf_file

    all_chunks.extend(chunks)
    print(f"  -> {len(chunks)} chunks extraídos")

print(f"\nTotal de chunks: {len(all_chunks)}")

# ============================================================
# 3. Separar elementos em tabelas, textos e imagens
# ============================================================
tables = []
texts = []

for chunk in all_chunks:
    if "Table" in str(type(chunk)):
        tables.append(chunk)
    if "CompositeElement" in str(type(chunk)):
        texts.append(chunk)

images = []
image_sources = []
for chunk in all_chunks:
    if "CompositeElement" in str(type(chunk)):
        for el in chunk.metadata.orig_elements:
            if "Image" in str(type(el)):
                images.append(el.metadata.image_base64)
                image_sources.append({
                    "filename": getattr(el.metadata, "filename", "desconhecido"),
                    "page_number": getattr(el.metadata, "page_number", None),
                })

print(f"Textos: {len(texts)} | Tabelas: {len(tables)} | Imagens: {len(images)}")

# ============================================================
# 4. Gerar resumos com OpenAI
# ============================================================
model = ChatOpenAI(
    model="gpt-4o-mini",
)

# Resumos de texto e tabelas
prompt_text = """
Você é um assistente responsável por resumir tabelas e textos.
Faça um resumo conciso da tabela ou texto.

Responda apenas com o resumo, sem comentários adicionais.
Não comece sua mensagem dizendo "Aqui está um resumo" ou algo parecido.
Apenas forneça o resumo diretamente.

Tabela ou trecho de texto: {element}
"""
prompt = ChatPromptTemplate.from_template(prompt_text)
summarize_chain = {"element": lambda x: x} | prompt | model | StrOutputParser()

print("Resumindo textos...")
text_summaries = []
filtered_texts = []
for i, text in enumerate(texts):
    try:
        summary = summarize_chain.invoke(text)
        text_summaries.append(summary)
        filtered_texts.append(text)
    except BadRequestError as e:
        print(f"  ⚠ Texto {i+1}/{len(texts)} bloqueado pelo filtro de conteúdo. Pulando...")
texts = filtered_texts

print("Resumindo tabelas...")
tables_html = [table.metadata.text_as_html for table in tables]
table_summaries = []
filtered_tables_html = []
filtered_tables = []
for i, html in enumerate(tables_html):
    try:
        summary = summarize_chain.invoke(html)
        table_summaries.append(summary)
        filtered_tables_html.append(html)
        filtered_tables.append(tables[i])
    except BadRequestError as e:
        print(f"  ⚠ Tabela {i+1}/{len(tables_html)} bloqueada pelo filtro de conteúdo. Pulando...")
tables = filtered_tables
tables_html = filtered_tables_html

# Resumos de imagens
prompt_image = """Descreva a imagem em detalhe. Para contexto,
                  a imagem faz parte de documentos sobre arquitetura
                  de software. Seja específico sobre gráficos, diagramas e tabelas."""
messages = [
    (
        "user",
        [
            {"type": "text", "text": prompt_image},
            {
                "type": "image_url",
                "image_url": {"url": "data:image/jpeg;base64,{image}"},
            },
        ],
    )
]
image_prompt = ChatPromptTemplate.from_messages(messages)
image_chain = image_prompt | model | StrOutputParser()

print("Resumindo imagens...")
image_summaries = []
filtered_images = []
for i, image in enumerate(images):
    try:
        summary = image_chain.invoke({"image": image})
        image_summaries.append(summary)
        filtered_images.append(image)
    except BadRequestError as e:
        print(f"  ⚠ Imagem {i+1}/{len(images)} bloqueada pelo filtro de conteúdo. Pulando...")
images = filtered_images

# ============================================================
# 5. Criar banco vetorial e armazenar dados
# ============================================================
embedding_function = OpenAIEmbeddings(
    model="text-embedding-3-small",
)

vectorstore = Chroma(
    collection_name="multi_modal_rag",
    embedding_function=embedding_function,
    persist_directory=os.path.join(base_dir, "chroma_db"),
)

id_key = "doc_id"

# Adicionar textos (resumo como page_content, original nos metadados)
if texts and text_summaries:
    doc_ids = [str(uuid.uuid4()) for _ in texts]
    summary_texts = [
        Document(
            page_content=summary,
            metadata={
                id_key: doc_ids[i],
                "tipo": "texto",
                "original_content": str(texts[i]),
                "filename": getattr(texts[i].metadata, "filename", "desconhecido"),
                "page_number": str(getattr(texts[i].metadata, "page_number", "")),
            },
        )
        for i, summary in enumerate(text_summaries)
    ]
    vectorstore.add_documents(summary_texts)
    print(f"Textos adicionados: {len(texts)}")

# Adicionar tabelas (resumo como page_content, HTML original nos metadados)
if tables and table_summaries:
    table_ids = [str(uuid.uuid4()) for _ in tables]
    summary_tables = [
        Document(
            page_content=summary,
            metadata={
                id_key: table_ids[i],
                "tipo": "tabela",
                "original_content": tables_html[i],
                "filename": getattr(tables[i].metadata, "filename", "desconhecido"),
                "page_number": str(getattr(tables[i].metadata, "page_number", "")),
            },
        )
        for i, summary in enumerate(table_summaries)
    ]
    vectorstore.add_documents(summary_tables)
    print(f"Tabelas adicionadas: {len(tables)}")

# Adicionar imagens (resumo como page_content, base64 nos metadados)
if images and image_summaries:
    img_ids = [str(uuid.uuid4()) for _ in images]
    summary_img = [
        Document(
            page_content=summary,
            metadata={
                id_key: img_ids[i],
                "tipo": "imagem",
                "original_content": images[i],
                "filename": image_sources[i].get("filename", "desconhecido"),
                "page_number": str(image_sources[i].get("page_number", "")),
            },
        )
        for i, summary in enumerate(image_summaries)
    ]
    vectorstore.add_documents(summary_img)
    print(f"Imagens adicionadas: {len(images)}")

print(f"\nBanco vetorial criado com sucesso em {os.path.join(base_dir, 'chroma_db')}")
