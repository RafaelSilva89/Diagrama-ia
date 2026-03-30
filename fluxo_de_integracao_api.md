# Fluxo de Integração API: Monolito para Microserviço 🚀

Neste documento, explicaremos como a plataforma se comporta na arquitetura de microserviços e onde encontrar cada um dos endpoints disponíveis para consumo pelo API Gateway e Frontend.

---

## 1. O Papel dos Participantes (Componentes)

*   **Front-End / TELA:** Aplicação React/Vue etc., onde o usuário interage visualmente.
*   **API Gateway:** Ponto único de entrada. Todas as requisições passam por ele. Ele valida o token de acesso e encaminha a requisição com a identidade do usuário (Header `X-User-Id`).
*   **Microserviço Django (Este projeto):** Responsável por gerir os metadados dos Projetos, Links das Imagens dos Diagramas, e pelo processamento da Inteligência Artificial (LangChain + RAG).
*   **Armazenamento (S3/Media):** Local físico onde os binários (imagens e PDFs) são guardados.

---

## 2. Diagrama Visual do Fluxo Completo

Abaixo, o fluxo de vida ponta a ponta desde que o usuário tenta logar até ele receber análise do diagrama. Note como o Gateway é a ponte obrigatória.

```text
[ USUÁRIO / FRONT-END ]
      │
      ├──► 1. Faz Login ──────────────► [ API GATEWAY ]
      │                                       │ (Valida credenciais/Gera Token JWT)
      │                                       └─► (Se não for o próprio Gateway que autentica)
      │                                           POST /usuarios/login/ ──► [ DJANGO ]
      │
      ├──► 2. Cria Projeto Clicando ──► [ API GATEWAY ] 
      │       em "Novo Projeto"               │ (Injeta Header: X-User-Id: 1)
      │                                       └─► POST /usuarios/projetos/ ──► [ DJANGO ]
      │
      ├──► 3. Faz Upload Diagrama ────► [ API GATEWAY ]
      │       (Multipart/form-data)           │ (Repassa binário da Imagem)
      │                                       └─► POST /usuarios/projeto/<id> ──► [ DJANGO ]
      │                                                ┌─────────────────────────────────┐
      │                                                │ [ DJANGO ] Salva imagem no disco│
      │                                                └─────────────────────────────────┘
      │
      ├──► 4. Clica "Analisar" ───────► [ API GATEWAY ]
      │                                       │
      │                                       └─► POST /ia/processar_analise/<id> ──► [ DJANGO ]
      │                                                ┌─────────────────────────────────┐
      │                                                │ [ DJANGO ] Aciona LangChain +   │
      │                                                │ OCR + Base RAG (Pinecone, etc.) │
      │                                                │ Aguarda Processamento           │
      │                                                │ Salva no Banco                  │
      │                                                └─────────────────────────────────┘
      │                                       ◄── (Retorna 201 Created quando finaliza)
      │
      ◄─── 5. Front lê o Resultado ───  [ API GATEWAY ] ◄── GET /ia/analise_diagrama/<id>
```

---

## 3. Endpoints no Microserviço Django

No Django, todas as rotas (endpoints) são declaradas nos arquivos `urls.py`. 

### A) Microserviço de Usuários & Projetos (`usuarios/urls.py`)
Responsável pelas regras de negócio ligadas à conta do Cliente e seus diagramas vinculados. 

*   `POST /usuarios/cadastro/` → (`views.cadastro`)
*   `POST /usuarios/login/` → (`views.login`)
*   `GET  /usuarios/projetos/` → (`views.projetos`) *(Lista os Projetos do usuário)*
*   `POST /usuarios/projetos/` → (`views.projetos`) *(Cria um Novo Projeto)*
*   `GET  /usuarios/projeto/<id>` → (`views.projeto`) *(Detalhes de 1 Projeto + seus diagramas)*
*   **`POST /usuarios/projeto/<id>`** → (`views.projeto`) *(Upload restrito de `form-data` p/ salvar o binário do Diagrama)*
*   `DELETE /usuarios/deletar-diagrama/<id>` → (`views.deletar_diagrama`)

> **Interligação c/ o Gateway:** Para qualquer interação que exija saber quem é o dono (nas funções de Listar, Criar ou Ver projetos), o gateway injeta no Request Headers a chave `X-User-Id: <id-do-banco>`. Isso faz com que a sessão tradicional baseada em cookies seja inútil.

### B) Microserviço de Integligência (Análise) (`ia/urls.py`)
Responsável pelo pipeline pesado de extração visual e requisições p/ LLMs.

*   `POST /ia/processar_analise/<id_diagrama>` → (`views.processar_analise`) *(Tríade LangChain + VectorDB + Infra OCR. Trata falhas e devolve summary do que achou).*
*   `GET  /ia/analise_diagrama/<id_diagrama>` → (`views.analise_diagrama`) *(Recupera do Banco local a análise que foi persistida, retornando a JSON contendo todos os alertas identificados e trilhas sugeridas).*
*   `GET  /ia/exportar_pdf/<id_diagrama>` → (`views.exportar_pdf`) *(Baixa os relatórios no formato PDF em binário puro servido via `FileResponse`).*

---

## 4. Como Connectar Tudo na Produção (Resumo Rápido)

1.  No API Gateway (ex: Kong, AWS API Gateway, NGINX):
    *   Defina as rotas `/usuarios/*` para apontar p/ o servidor Django (App de Usuários).
    *   Defina as rotas `/ia/*` para apontar p/ o mesmo servidor Django (App IA).
2.  Configure o Gateway para validar Tokens JWT. Em cada fluxo aprovado no JWT, extraia o `user_id` e introduza-o no Cabeçalho `X-User-Id` antes de repassar ao Django.
3.  Desabilite no Django (já feito na refatoração) a proteção nativa de CSRF via anotações `@csrf_exempt`, confiando assim nos bloqueios de entrada que o Gateway estará implementando.