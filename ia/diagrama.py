"""
Gera um infografico profissional a partir de um diagrama tecnico
utilizando o modelo Gemini 2.5 Flash com capacidade de geracao de imagem.

"""

import os
from io import BytesIO

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

# Carrega as variaveis de ambiente do arquivo .env
load_dotenv()


def extrair_imagens_geradas(response):
    """Extrai as imagens geradas a partir da resposta da API do Gemini.

    Percorre as partes da resposta e converte os dados binarios
    em objetos PIL.Image.
    """
    imagens = []
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            imagens.append(Image.open(BytesIO(part.inline_data.data)))
    return imagens


def gerar_infografico_from_path(caminho_entrada, caminho_saida, sugestoes=None):
    """Gera infografico a partir de um diagrama e salva no caminho especificado.

    Args:
        caminho_entrada: Caminho absoluto da imagem do diagrama original
        caminho_saida: Caminho absoluto onde salvar a imagem gerada
        sugestoes: Lista de strings com sugestoes/correcoes a aplicar no diagrama

    Returns:
        Caminho da imagem gerada ou None em caso de erro
    """
    try:
        client = genai.Client(
            api_key=os.environ["GOOGLE_API_KEY"],
        )

        imagem_diagrama = Image.open(caminho_entrada)

        prompt = """
        Transform this technical software architecture diagram into a professional, high-quality infographic.
        The design should be modern and clean.
        Maintain all the original components and their connections exactly as shown in the diagram.
        - Use a professional color palette (e.g., shades of tech-blue, slate gray, and white).
        - Ensure the arrows and flow of information are sharp and easy to follow.
        - The background should be a clean, neutral gradient or a very subtle technical grid.
        - Keep the text labels clear, using a modern sans-serif font.
        """

        if sugestoes:
            prompt += "\n\nApply the following improvements to the diagram:\n"
            for sugestao in sugestoes:
                prompt += f"- {sugestao}\n"

        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[imagem_diagrama, prompt],
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        imagens_geradas = extrair_imagens_geradas(response)

        if not imagens_geradas:
            return None

        os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
        imagens_geradas[0].save(caminho_saida)
        return caminho_saida

    except Exception as e:
        print(f"Erro ao gerar infografico: {e}")
        return None
