import json
import threading
import requests
import os
import time
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.files.base import ContentFile

from usuarios.models import Diagrama, Projeto
from .models import AnaliseDiagrama
from .agent_langchain import DiagramaAI
from .views import _enriquecer_com_rag
from .diagrama import gerar_infografico_from_path

# URLs dos microservicos (idealmente colocar no .env)
BUCKET_SERVICE_URL = os.environ.get('BUCKET_SERVICE_URL', 'http://bucket-service/bucket/download')
OPERATOR_SERVICE_URL = os.environ.get('OPERATOR_SERVICE_URL', 'http://operator-service/operator/report')

@csrf_exempt
def api_create_diagram(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nome = data.get('name', 'Sem nome')
            file_ids = data.get('files', [])
            
            # Necessario vincular a um projeto/usuario existente (ou criar um mock para o Bot)
            projeto = Projeto.objects.first()
            if not projeto:
                from django.contrib.auth.models import User
                user = User.objects.first()
                if not user:
                    user = User.objects.create(username="bot_api")
                projeto = Projeto.objects.create(nome="Projeto API", user=user)

            # Cria o diagrama sem o arquivo por enquanto (sera baixado no processamento)
            # Salva o id do arquivo no S3 em algum campo, aqui usaremos o nome como referencia
            diagrama = Diagrama(projeto=projeto)
            
            # Precisamos salvar *alguma* coisa no FileField para nao dar erro, ou o download acontece aqui
            # Vamos gerar um txt vazio como placeholder da imagem por enquanto
            diagrama.arquivo.save(f"placeholder_{nome}.png", ContentFile(b""))
            diagrama.save()
            
            # Podemos salvar os file_ids em algum lugar para o job em background ler depois
            
            return JsonResponse({'id': diagrama.id}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def processar_diagrama_background(diagram_id, file_id):
    """
    Funcao que roda em background (Thread ou Celery).
    1. Busca imagem no Bucket
    2. Processa na IA
    3. Envia Relatorio ao Operador
    """
    try:
        diagrama = Diagrama.objects.get(id=diagram_id)
        start_time = time.time()
        
        # 1. Faz o download do arquivo no BUCKET
        bucket_url = f"{BUCKET_SERVICE_URL}/{file_id}"
        
        try:
            response_bucket = requests.get(bucket_url, timeout=5)
            if response_bucket.status_code == 200:
                # Substitui o placeholder pelo arquivo real recebido do Bucket
                file_name = f"diagrama_baixado_{diagram_id}.png"
                diagrama.arquivo.save(file_name, ContentFile(response_bucket.content))
                diagrama.save()
            else:
                print(f"Erro ao baixar arquivo no bucket: {response_bucket.status_code}")
                return
        except requests.exceptions.RequestException as e:
            print(f"Aviso: Falha ao conectar no bucket-service. Usando imagem do HD (mock_diagrama).")
            # Usa o arquivo 'diagrama.png' do seu HD como imagem de teste
            mock_path = os.path.join(settings.BASE_DIR, 'diagrama.png')
            if os.path.exists(mock_path):
                with open(mock_path, 'rb') as f:
                    file_name = f"diagrama_mock_{diagram_id}.png"
                    diagrama.arquivo.save(file_name, ContentFile(f.read()))
                    diagrama.save()
            else:
                print(f"Arquivo '{mock_path}' não encontrado. O RAG / Langchain não terá imagem para testar.")
                return
            
        # 2. Processamento IA
        agent = DiagramaAI()
        content = agent.prepare_content(diagrama.arquivo.path)

        max_tentativas = 3
        response = None
        for tentativa in range(1, max_tentativas + 1):
            response = agent.run(content)
            campos_preenchidos = all([
                response.erros_coerencia,
                response.riscos_identificados,
                response.problemas_estrutura,
                response.red_flags,
            ])
            if campos_preenchidos or tentativa == max_tentativas:
                break

        # Enriquecer com RAG
        erros_enriquecidos, fontes_erros = _enriquecer_com_rag(response.erros_coerencia, "erros de coerencia e lacunas")
        riscos_enriquecidos, fontes_riscos = _enriquecer_com_rag(response.riscos_identificados, "riscos de design")
        estrutura_enriquecida, fontes_estrutura = _enriquecer_com_rag(response.problemas_estrutura, "problemas de estrutura")
        red_flags_enriquecidas, fontes_red_flags = _enriquecer_com_rag(response.red_flags, "red flags criticas")

        indice = response.indice_risco
        classificacao = "Baixo" if indice <= 30 else "Medio" if indice <= 60 else "Alto" if indice <= 80 else "Critico"

        fontes_rag = {
            "erros_coerencia": fontes_erros,
            "riscos_identificados": fontes_riscos,
            "problemas_estrutura": fontes_estrutura,
            "red_flags": fontes_red_flags,
        }

        analise, created = AnaliseDiagrama.objects.update_or_create(
            diagrama=diagrama,
            defaults={
                'indice_risco': indice,
                'classificacao': classificacao,
                'erros_coerencia': erros_enriquecidos,
                'riscos_identificados': riscos_enriquecidos,
                'problemas_estrutura': estrutura_enriquecida,
                'red_flags': red_flags_enriquecidas,
                'fontes_rag': fontes_rag,
                'tempo_processamento': int(time.time() - start_time),
            }
        )

        # 3. Enviar relatorio ao OPERADOR
        payload_operador = {
            "id": diagrama.id,
            "report": {
                "riscs": str(riscos_enriquecidos),
                "erros": str(erros_enriquecidos),
                "structure": str(estrutura_enriquecida),
                "redFlags": str(red_flags_enriquecidas),
                "generalRiscs": f"Indice: {indice} - {classificacao}"
            }
        }
        
        headers = {'Content-Type': 'application/json'}
        try:
            resposta_op = requests.post(OPERATOR_SERVICE_URL, json=payload_operador, headers=headers, timeout=5)
            print(f"Relatório enviado ao operador, status: {resposta_op.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Aviso: Não foi possível conectar ao operator-service para enviar o relatório final. (Mock local concluído)")

    except Exception as e:
        print(f"Erro no processamento background: {str(e)}")


@csrf_exempt
def api_process_diagram(request, id):
    if request.method == 'POST':
        # Retorna 204 No Content imediatamente
        # Inicia o processamento numa thread (assumindo file_id mockado se não salvo no banco)
        # O ideal serial passar o file_id pelo request ou buscar do DB.
        
        # Para fins de exemplo, pegamos um file_id hardcoded ou recuperamos do BD.
        file_id = 12 
        
        thread = threading.Thread(target=processar_diagrama_background, args=(id, file_id))
        thread.start()
        
        return JsonResponse({}, status=204)
        
    return JsonResponse({'error': 'Method not allowed'}, status=405)
