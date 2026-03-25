# Entendendo o Fluxo da Aplicação: A Jornada do seu Diagrama

Este documento tem como objetivo explicar, passo a passo e de forma bastante visual, como e quando os sistemas ("microserviços") conversam entre si desde o momento em que o usuário anexa uma imagem na tela até a hora em que recebe o relatório pronto da Inteligência Artificial.

---

## Conceitos Básicos

Antes de olharmos para o fluxo, aqui estão dois conceitos para facilitar a leitura:

1. **Endpoint (Ponto de Extremidade):** É como se fosse o "guichê de atendimento" de um sistema. Quando um sistema quer pedir algo para outro, ele "bate na porta" desse guichê. 
2. **Tipos de Chamada:**
   - **GET:** É o ato de  *buscar* (fazer o *download* de algo).
   - **POST:** É o ato de *enviar* uma informação nova para ser calculada ou gravada.

---

## Desenho do Fluxo (Diagrama Visual)

Para ilustrar o momento que cada guichê (endpoint) é acionado, vamos ver a conversa entre o Usuário e os sistemas:




[ USUÁRIO ] 
    │
    ├─► 1. Clica em "Salvar" ──► [ GATEWAY / TELA ]
                                        │
                                        ├─► Salva Foto ──────────► ( BUCKET / S3 )
                                        │
                                        └─► POST /api/diagram ───► [ BOT / IA (Django) ]
                                                                       *(Gera ID no Banco)*

    ├─► 2. Clica "Analisar" ───► [ GATEWAY / TELA ]
                                        │
                                        └─► POST /process ───────► [ BOT / IA (Django) ]
                                                                       *(Responde 204 na hora)*
                                                                               │
       (O Bot / IA começa a rodar a Inteligência em Segundo Plano) ◄───────────┘
                                        │
    . . . . . . . . . . . . . . . . . . │ . . . . . . . . . . . . . . . . . . . . . . .
    . BASTIDORES (Lógica da IA)         │                                             .
    .                                   ├─► GET /download ───────► ( BUCKET / S3 )    .
    .                                   │    *(Busca a foto para a IA ler...)*        .
    .                                   │                                             .
    .                                   └─► POST /operator/report► [ OPERADOR ]       .
    . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 
                                                                         │
                                       [ GATEWAY / TELA ] ◄──────────────┘
    ◄─── 4. Mostra Resultado Final ────┘
```

---

## O Passo a Passo Detalhado (Momento a Momento)

Aqui está a tradução do desenho acima com mais detalhes sobre a experiência do usuário:

### Momento 1: Salvando e Guardando o Arquivo
* **Na Tela:** O usuário anexa a imagem do seu fluxograma/arquitetura e clica em **"Salvar"**.
* **Nos Bastidores:** A tela (através do API Gateway) joga essa imagem pesada num "galpão de arquivos" chamado **Bucket (S3)**. Em seguida, o Gateway dá um toque no seu projeto Django: 
  * 👉 *"O endpoint **`POST /api/diagram`** é acionado."*
* **A Reação do nosso Bot/IA:** Ele cria a ficha do diagrama no banco de dados com os IDs da imagem, mas ainda não leu a imagem.

### Momento 2: Apertando o botão de "Analisar Diagrama"
* **Na Tela:** O usuário não quer só salvar, ele agora quer a opinião da IA e aperta em **"Analisar Diagrama"**. A tela dele muda para uma barrinha rodando ("Carregando...").
* **Nos Bastidores:** O sistema precisa mandar a IA trabalhar sem travar as coisas. A tela fala pro Bot:
  * 👉 *"O endpoint **`POST /api/diagram/<id>/process`** é acionado."*
* **A Reação do nosso Bot/IA:** O Bot é inteligente. Ele manda a IA começar a trabalhar no cantinho (em segundo plano) e grita imediatamente de volta para a tela: *"Beleza, já está na fila! Pode mostrar a animação de carregamento (204 No Content)"*.

### Momento 3: A IA Baixa a Imagem e Começa a Ler
* **Na Tela:** O usuário ainda está vendo o "Carregando...".
* **Nos Bastidores:** Agora que a IA no Django acordou, a primeira coisa que ela nota é: *"Eu não tenho a imagem, ela está lá no galpão!"*.
  * 👉 *"O nosso Bot aciona o Microserviço focado em downloads: **`GET /bucket/download/<id>`**".*
* **A Reação:** O galpão do Bucket manda a imagem. A sua função Langchain abre a imagem e começa a ler os textos, encontrar vazamentos, falhas de segurança e problemas na arquitetura.

### Momento 4: Terminando o Dever de Casa
* **Na Tela:** A barrinha de carregando de repente termina e aparece a nota (Risco Crítico, Risco Baixo), com a tela cheia de dicas.
* **Nos Bastidores:** Assim que o motor do Gemini termina de escrever tudo, o nosso Bot/IA precisa desovar essa informação gigantesca no lugar certo. Ele não pode guardar só pra ele, ele conta pro Diretor do Sistema (o Operador).
  * 👉 *"O nosso Bot aciona o endpoint **`POST /operator/report`** no microserviço do Operador".*
* **A Reação:** O JSON gigante empacotado pelo Bot com a análise estruturada chega no Operador. O Operador grava, avisa a tela do Usuário e tudo finaliza com sucesso!

---

## Resumo Decifrado para Leigos (O Que Entra e O Que Sai do Django)

Para simplificar a ideia de **GET** e **POST**, imagine que o seu código Django (Bot/IA) é uma loja.

* **Endpoints de Entrada (As portas que abrimos na sua loja)**
  * Recebemos uma encomenda (criar registro): **`POST /api/diagram`**
  * Recebemos uma ordem de trabalho (pedir pra pensar): **`POST /api/diagram/<id>/process`**

* **Endpoints de Saída (O motoboy que a sua loja manda pra rua)**
  * Pedir material pro vizinho (Pegar imagem do Bucket S3): **`GET /bucket/download/<id>`**
  * Entregar produto pronto pro vizinho (Entregar o Relatório pro Operador): **`POST /operator/report`**

---

## Como Testar na Prática (Guia para Postman/Insomnia)

Para ver a nossa API do Bot/IA funcionando no seu computador (sem depender das telas do Frontend prontas), você pode simular os chamados utilizando o aplicativo **Postman**. 

Veja exatamente como preencher o aplicativo:

### Teste 1: Criar um novo Diagrama (O Input do Gateway)
Simula o momento em que a imagem foi salva no Bucket e nós (Bot) somos notificados.

* **Método HTTP:** Troque para `POST`
* **URL:** `http://127.0.0.1:8000/api/diagram` *(supondo que seu django roda na porta 8000)*
* Aba **Body** -> Marque **raw** -> Mude de Text para **JSON**.
* Conteúdo a colar:
```json
{
  "name": "Arquitetura Nova de Vendas",
  "files": [12, 18, 32]
}
```
* Clique em **"Send"**.
* **O Resultado:** O Postman vai devolver o código `201 Created` e você verá a criação do id no seu painel inferior como na vida real:
```json
{
  "id": 1234
}
```

### Teste 2: Iniciar a Análise do Diagrama
Simula o momento do clique no botão "Analisar". A mágica começa aqui.

* **Método HTTP:** Troque para `POST`
* **URL:** `http://127.0.0.1:8000/api/diagram/1234/process` *(Substitua "1234" pelo ID que você gerou no Teste 1)*
* Aba **Body:** Deixe sem nada (Selecione a opção **none**).
* Clique em **"Send"**.
* **O Resultado Imediato:** A resposta no Postman chega em alguns milissegundos mostrando o código verde **`204 No Content`** e fica em branco. Isso quer dizer que "recebemos a ordem e já demos início".

### Teste 3: Acompanhando o Relatório Sendo Entregue
Como no Teste 2 a tela do Postman foi liberada quase imediatamente (204), a Inteligência Artificial começa a trabalhar de olhos fechados no segundo plano (no background).

Onde conferir se está rodando? Olhe a janela preta do seu terminal onde o `python manage.py runserver` está ativo.

Quando o processamento Langchain terminar (Pode demorar uns 20 segundos dependendo da IA), o sistema vai, **sozinho**, preparar e enviar um super arquivo JSON pro servidor do Operador avisando do fim do processo. 

**O JSON gigantesco que o nosso Bot manda ATIVAMENTE para o Operador tem esta exata estrutura:**
```json
{
  "id": 1234,
  "report": {
    "riscs": "[{'titulo': 'Risco alto de travamento...', 'fundamentacao': '...'}]",
    "erros": "[{'titulo': 'Falta da conexão entre Frontend e API...', 'fundamentacao': '...'}]",
    "structure": "[{'titulo': 'Legenda Incompleta no DB...', 'fundamentacao': '...'}]",
    "redFlags": "[{'titulo': 'Conexão aberta sem Autenticação...', 'fundamentacao': '...'}]",
    "generalRiscs": "Indice: 75 - Alto"
  }
}
```
*(É esse formato JSON que a equipe conectada ao serviço Operador está aguardando nós entregarmos nas mãos deles!)*
