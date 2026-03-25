# Projeto IA - Análise e Avaliação de Diagramas (Microserviço Bot)

Este é o módulo especialista em **Inteligência Artificial** do sistema. Ele atua como um Arquiteto de Software automatizado: recebe imagens de diagramas de arquitetura, diagrama de classes ou fluxogramas, interpreta o desenho e gera um relatório crítico e embasado sobre possíveis falhas estruturais, riscos de design e problemas de segurança.

Este projeto foi construído em Python com **Django**, utilizando o ecossistema do **Langchain** para orquestração de LLMs e integrações avançadas de **RAG (Retrieval-Augmented Generation)**. A sua arquitetura foi desenhada para atuar como um *Microserviço*, comunicando-se de forma assíncrona através de APIs REST com outros blocos do sistema.

---

## 1. A Experiência do Usuário na Plataforma

Do ponto de vista de quem usa a aplicação final, este motor de IA atua de forma invisível mas poderosa ao longo de toda a jornada:

1. **Cadastro e Organização:** O usuário inicia fazendo o seu cadastro na plataforma. Após o login, ele realiza a **Criação de um Projeto**. Cada projeto criado funciona como uma pasta, onde ele poderá fazer o upload de *vários diagramas* diferentes associados àquele escopo.
2. **Upload do Diagrama:** O usuário faz o upload da imagem do seu diagrama (ex: banco de dados na nuvem ou sistemas de API) para dentro do projeto escolhido através do *Frontend*.
3. **Solicitação de Análise:** Com o diagrama salvo, o usuário solicita a avaliação especializada com um clique. A tela exibe um aviso de "Analisando / Carregando...", indicando que o processo denso começou nos bastidores.
4. **Recebimento de Insights Claros:** Após alguns segundos, a tela se atualiza sozinha e o usuário recebe um Raio-X detalhado da sua arquitetura, contendo:
   * **Índice de Risco Geral:** Uma nota rápida e colorida (Ex: *Risco Alto - 75*).
   * **Problemas de Coerência, Riscos de Design e Red Flags Críticas:** Avisos gravíssimos como falhas de segurança explícita ou anti-padrões severos.
5. **Re-análises e Exportação:** Se o usuário corrigir o diagrama (fizer um novo upload), ele pode usar a opção de **Reanalisar** para verificar a melhoria. Além disso, existe a opção de **Salvar em PDF** para exportar o laudo técnico completo contendo o diagnóstico da IA e as regras do banco de conhecimento (RAG).

---

## 2. Como Funciona a Inteligência Artificial e o RAG

O coração técnico desta aplicação não se limita a "fazer uma pergunta para uma IA comum". Existe uma esteira de análise sofisticada estruturada nos seguintes pilares:

### A. Modelos Híbridos (OpenAI e Nanobanana)
Para extrair o melhor de cada ferramenta e otimizar custos, o sistema processa imagens e textos utilizando duas das melhores tecnologias disponíveis: o cruzamento entre chamadas da **OpenAI** (para extrema precisão de raciocínio lógico em cenários de alta complexidade) e a eficiência do **Nanobanana** (modelos rápidos e especializados).  

### B. Agentes Especialistas (Langchain) e Guardrails
A aplicação age com *Prompts* direcionados onde o modelo assume a *persona* de um arquiteto de software de alto nível. Antes de qualquer resposta do modelo de linguagem ser devolvida, a saída passa por um rigoroso sistema de **Guardrails** (trilhos de segurança e filtros de IA). Esses guardrails garantem que a IA **não invente/alucine** problemas que não existem na imagem, filtram respostas foras de escopo técnico e forçam a moldagem da saída no formato perfeitamente estruturado (`JSON` puro).

### C. Enriquecimento Técnico com RAG (Retrieval-Augmented Generation)
Para garantir que as avaliações sejam validadas e 100% literais (de acordo com diretrizes de engenharia), quando a IA e os modelos de Visão levantam um problema estrutural no diagrama, esse problema é consultado pelo nosso motor em um **Banco Vetorial (RAG)**. 
O RAG mergulha nos manuais de melhores práticas e metodologias, mesclando a suspeita visual da IA com o fundamento da literatura (Ex: injetando "*A AWS recomenda que Bancos RDS não fiquem em Subnets Públicas, Fonte: AWS Arch Guide page 32*") no envio final do problema.

---

## 3. Os Endpoints e a Conexão com Microserviços

Sendo um microserviço *Backend* (`Bot / IA`), a comunicação com o resto da plataforma digitaliza-se através de requisições HTTP REST. Abaixo está a documentação das direções e payloads.

### Endpoints de ENTRADA (O que a nossa IA recebe)

* **`POST /api/diagram`**: Cadastra um "protocolo" de que existe uma nova imagem esperando processamento.
  * **Formato do JSON (Payload Recebido):**
    ```json
    {
      "name": "Diagrama de Pagamentos AWS",
      "files": [88, 12, 44]
    }
    ```
  * **Retorno:** `{"id": 1234}` (HTTP 201 Created)

* **`POST /api/diagram/{id}/process`**: É o gatilho que avisa nosso Bot a ligar o motor da IA escondido no Background.
  * **Formato do JSON:** Nenhum payload (`{}` ou Vazio).
  * **Retorno:** Responde instantaneamente `204 No Content` para libertar a tela do usuário da trava de carregamento.

### Endpoints de SAÍDA (O que a nossa IA empurra para outros serviços)

* **`GET http://[BUCKET-SERVICE]/download/{id}`**: Requisição interna (*request.get*) disparada dentro do *Background*. Ela vai no serviço de Arquivos buscar a imagem crua do Gateway para que o Langchain possa ler.
* **`POST http://[OPERATOR-SERVICE]/report`**: Após horas (ou segundos) de cálculos em nosso motor do `agent_langchain.py`, o relatório consolidado pronto e verificado pelos Guardrails é devolvido ativamente para o Operador.
  * **Formato do JSON (Payload Enviado de Saída):**
    ```json
    {
      "id": 1234,
      "report": {
        "riscs": "[{'titulo': 'Risco alto identifico...', 'fundamentacao': '...'}]",
        "erros": "[{'titulo': 'Conexão Frontend-DB direta...', 'fundamentacao': '...'}]",
        "structure": "[{'titulo': 'Sem gateway configurado...', 'fundamentacao': '...'}]",
        "redFlags": "[{'titulo': 'Aviso crítico de segurança...', 'fundamentacao': '...'}]",
        "generalRiscs": "Indice: 75 - Alto"
      }
    }
    ```

---

## 4. Diagrama de Fluxo Macro do Projeto

Para facilitar o entendimento holístico, veja o fluxograma técnico do processo de ponta a ponta (do Cadastro inicial até o momento em que se pode Salvar o PDF):

```text
[ USUÁRIO ] 
    │
    ├─► 1. Cadastra Projeto e Upload de Diagramas ──► [ PLATAFORMA FRONTEND ]
                                                              │
                                                              ├─► 3. Salva Imagem ──────► ( BUCKET / S3 )
                                                              │
                                                              └─► 4. POST /diagram ─────► [ BOT / IA (Django) ]
                                                                                              *(Devolve o ID)*
                                              
    ├─► 5. Clica no botão "Analisar" ───────────────► [ PLATAFORMA FRONTEND ]
                                                              │
                                                              └─► 6. POST /process ─────► [ BOT / IA (Django) ]
                                                                                              *(Retorna 204 Rápido)*
                                                                                                      │
           (A Inteligência Artificial começa a rodar pesadamente nos bastidores) ◄────────────────────┘
                                        │
    ╔═══════════════════════════════════╧════════════════════════════════════════════╗
    ║ MOTORES DA INTELIGÊNCIA ARTIFICIAL (Trabalhando em Background)                 ║
    ║                                                                                ║
    ║   [ BOT ] ── 7. GET /download ──► ( BUCKET S3 )                                ║
    ║      │                            *(Busca a imagem em alta qualidade...)*      ║
    ║      ▼                                                                         ║
    ║   [ LANGCHAIN & MODELOS HÍBRIDOS (OPENAI / NANOBANANA) ]                       ║
    ║      │   (A visão computacional analisa o diagrama profundamente)              ║
    ║      ▼                                                                         ║
    ║   [ RAG (Banco Vetorial) ]                                                     ║
    ║      │   (Pesquisa regras e fundamentações técnicas p/ os erros achados)       ║
    ║      ▼                                                                         ║
    ║   [ GUARDRAILS ]                                                               ║
    ║      │   (Valida para evitar alucinações e empacota tudo em formato JSON)      ║
    ║      ▼                                                                         ║
    ║   [ BOT ] ── 9. POST /report ───► [ OPERADOR / API GATEWAY ]                   ║
    ║                                   *(Entrega o Relatório 100% pronto!)*         ║
    ╚════════════════════════════════════════════════════════════════════════════════╝
                                                     │
                                        [ PLATAFORMA FRONTEND ] ◄────────────────────┘
                                                     │
    ◄── 10. Mostra a Tela com Relatórios Complexos ──┘
    │
    └─► 11. Opcional: Clica em "Salvar em PDF" ──────► [ APP GERA O O DOCUMENTO FINAL ]
```
