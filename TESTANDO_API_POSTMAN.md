# Guia de Testes da API (Microserviço) no Postman

Este guia explica como testar os endpoints da aplicação Django refatorada para API JSON usando o Postman.

Assumimos que o servidor está rodando em `http://localhost:8000`. Se estiver em outra porta, substitua nas URLs abaixo.

---

## 1. Cadastro de Usuário
**Endpoint:** `POST http://localhost:8000/usuarios/cadastro/`
*   **Aba Body:** Selecione `raw` e no dropdown mude de `Text` para `JSON`.
*   **Conteúdo:**
```json
{
    "username": "usuario_teste",
    "senha": "password123",
    "confirmar_senha": "password123"
}
```
*   **Retorno Esperado:** Status `201 Created` e um JSON com `{"message": "Usuário criado com sucesso.", "user_id": 1}`. 
*   **Dica:** Anote o `user_id` retornado, pois você vai precisar dele nos próximos passos.

## 2. Login
**Endpoint:** `POST http://localhost:8000/usuarios/login/`
*   **Aba Body:** Selecione `raw` -> `JSON`.
*   **Conteúdo:**
```json
{
    "username": "usuario_teste",
    "senha": "password123"
}
```
*   **Retorno Esperado:** Status `200 OK` e um JSON confirmando o login e retornando o `user_id`.

---

## 3. Criar Novo Projeto
**Endpoint:** `POST http://localhost:8000/usuarios/projetos/`
*   **Aba Headers:** Adicione uma nova chave e valor:
    *   **Key:** `X-User-Id`
    *   **Value:** `1` *(use o ID do usuário que você anotou)*
*   **Aba Body:** Selecione `raw` -> `JSON`.
*   **Conteúdo:**
```json
{
    "nome": "Meu Primeiro Projeto"
}
```
*   **Retorno Esperado:** Status `201 Created` com o ID do projeto criado (`projeto_id`). Anote esse ID.

## 4. Listar Projetos
**Endpoint:** `GET http://localhost:8000/usuarios/projetos/`
*   **Aba Headers:** Adicione a chave:
    *   **Key:** `X-User-Id`
    *   **Value:** `1`
*   **Aba Body:** Selecione `none` (não precisa enviar corpo).
*   **Retorno Esperado:** Status `200 OK` com a lista de projetos em JSON.

---

## 5. Fazer Upload do Diagrama (ATENÇÃO, ESSE É DIFERENTE)
Como envio de arquivos binários não funciona bem em JSON puro, esse endpoint foi mantido como `form-data`.

**Endpoint:** `POST http://localhost:8000/usuarios/projeto/<id_projeto>` *(Substitua <id_projeto> pelo ID que você anotou no passo 3. Exemplo: `/usuarios/projeto/1`)*
*   **Aba Body:** Selecione **`form-data`** (não marque raw/JSON).
*   **Campos:**
    *   **Key:** Digite `diagrama`. Lá no canto direito da própria célula "diagrama", vai aparecer um botãozinho oculto escrito "Text". Clique nele e mude para **File**.
    *   **Value:** Clique no botão "Select Files" e escolha a imagem do seu diagrama no seu computador.
*   **Retorno Esperado:** Status `201 Created` informando que o diagrama foi salvo e retornando o `diagrama_id`. Anote o ID do diagrama!

## 6. Ver Detalhes do Projeto e Diagramas
**Endpoint:** `GET http://localhost:8000/usuarios/projeto/<id_projeto>`
*   **Aba Body:** `none`
*   **Retorno Esperado:** Status `200 OK` com o projeto e a lista de diagramas vinculados a ele.

---

## 7. Processar Análise do Diagrama (IA)
Esse endpoint aciona o agente LangChain para analisar o diagrama. Pode demorar alguns segundos.

**Endpoint:** `POST http://localhost:8000/ia/processar_analise/<id_diagrama>` *(Substitua <id_diagrama> pelo ID de diagrama recém criado)*
*   **Aba Body:** `none`
*   **Retorno Esperado:** Status `201 Created` informando sucesso, junto com os dados reduzidos da análise e tempo de processamento.

## 8. Ver Resultado Completo da Análise
**Endpoint:** `GET http://localhost:8000/ia/analise_diagrama/<id_diagrama>`
*   **Aba Body:** `none`
*   **Retorno Esperado:** Status `200 OK` com um JSON contendo todos os detalhes estruturados, fontes RAG, e o caminho da imagem de infográfico (se tiver sido gerada).

## 9. Exportar PDF
**Endpoint:** `GET http://localhost:8000/ia/exportar_pdf/<id_diagrama>`
*   **Retorno Esperado:** O Postman vai receber um arquivo binário.
*   **Como ver o PDF no Postman:** Quando a request finalizar e mostrar caracteres estranhos na reposta, no painel de Response (onde você vê o resultado), clique na setinha pra baixo do botão **"Save Response"** e selecione **"Save to a file"**. Escolha onde quer salvar no seu PC e abra o PDF.

---

### Resumo de Tipos de Dados (Headers x Body HTTP)

- **GET routes**: Nunca levam body. Usam a URL e, em alguns casos, headers (`X-User-Id`).
- **POST forms**: Na rota de upload (`/usuarios/projeto/<id>/`), use `form-data` na aba Body.
- **POST normais**: `/cadastro/`, `/login/`, criar projetos. Sempre na aba Body -> `raw` e mudar a caixa de listagem para `JSON`.
