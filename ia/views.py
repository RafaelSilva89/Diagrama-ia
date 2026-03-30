import os
import io
import time
import json

from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, FileResponse
from django.conf import settings
from usuarios.models import Diagrama
from .models import AnaliseDiagrama
from .agent_langchain import DiagramaAI
from .diagrama import gerar_infografico_from_path
from .consultar_banco_vetorial import consultar_rag


def _enriquecer_com_rag(items: list, categoria: str) -> tuple:
    """Enriquece uma lista de itens da analise com informacoes do RAG."""
    if not items:
        return [], []

    items_enriquecidos = []
    todas_fontes = []

    for item in items:
        item_dict = {
            "titulo": item,
            "texto": item,
            "fundamentacao": "",
            "fontes": [],
        }

        pergunta_item = (
            f"Para o seguinte problema em um diagrama de software: '{item}'. "
            f"Responda em no maximo 2-3 frases curtas: qual o conceito tecnico envolvido "
            f"e qual a acao corretiva recomendada. Sem definicoes academicas longas."
        )
        resultado_item = consultar_rag(pergunta_item)
        if resultado_item.get("valida") and resultado_item.get("resposta"):
            item_dict["fundamentacao"] = resultado_item["resposta"]
            fontes_item = resultado_item.get("fontes", [])
            if fontes_item:
                item_dict["fontes"] = fontes_item
                todas_fontes.extend(fontes_item)

        items_enriquecidos.append(item_dict)

    return items_enriquecidos, todas_fontes


@csrf_exempt
def analise_diagrama(request, id):
    try:
        diagrama = Diagrama.objects.get(id=id)
    except Diagrama.DoesNotExist:
        return JsonResponse({'message': 'Diagrama não encontrado.'}, status=404)

    analise = AnaliseDiagrama.objects.filter(diagrama=diagrama).first()
    
    if request.method == 'GET':
        dados_analise = None
        if analise:
            dados_analise = {
                'id': analise.id,
                'indice_risco': analise.indice_risco,
                'classificacao': analise.classificacao,
                'erros_coerencia': analise.erros_coerencia,
                'riscos_identificados': analise.riscos_identificados,
                'problemas_estrutura': analise.problemas_estrutura,
                'red_flags': analise.red_flags,
                'fontes_rag': analise.fontes_rag,
                'tempo_processamento': analise.tempo_processamento,
                'data_criacao': analise.data_criacao.strftime('%Y-%m-%dT%H:%M:%S'),
                'imagem_infografico': str(analise.imagem_infografico) if analise.imagem_infografico else None
            }
        
        return JsonResponse({
            'diagrama': {
                'id': diagrama.id,
                'arquivo': diagrama.arquivo.name,
                'projeto_id': diagrama.projeto.id
            },
            'analise': dados_analise
        }, status=200)

    return JsonResponse({'message': 'Método não permitido.'}, status=405)


@csrf_exempt
def processar_analise(request, id):
    if request.method != 'POST':
        return JsonResponse({'message': 'Método não permitido.'}, status=405)

    try:
        diagrama = Diagrama.objects.get(id=id)
    except Diagrama.DoesNotExist:
        return JsonResponse({'message': 'Diagrama não encontrado.'}, status=404)

    try:
        start_time = time.time()

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

        # Enriquecer cada campo com RAG
        erros_enriquecidos, fontes_erros = _enriquecer_com_rag(
            response.erros_coerencia, "erros de coerencia e lacunas"
        )
        riscos_enriquecidos, fontes_riscos = _enriquecer_com_rag(
            response.riscos_identificados, "riscos de design"
        )
        estrutura_enriquecida, fontes_estrutura = _enriquecer_com_rag(
            response.problemas_estrutura, "problemas de estrutura"
        )
        red_flags_enriquecidas, fontes_red_flags = _enriquecer_com_rag(
            response.red_flags, "red flags criticas"
        )

        processing_time = int(time.time() - start_time)

        indice = response.indice_risco
        if indice <= 30:
            classificacao = "Baixo"
        elif indice <= 60:
            classificacao = "Medio"
        elif indice <= 80:
            classificacao = "Alto"
        else:
            classificacao = "Critico"

        # Montar fontes RAG por secao
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
                'tempo_processamento': processing_time,
            }
        )

        # Gerar infografico com Gemini
        infografico_gerado = False
        erro_infografico = None
        try:
            relatorios_dir = os.path.join(settings.MEDIA_ROOT, 'relatorios')
            os.makedirs(relatorios_dir, exist_ok=True)
            caminho_saida = os.path.join(relatorios_dir, f'infografico_{diagrama.id}.png')

            sugestoes = (
                response.erros_coerencia
                + response.riscos_identificados
                + response.problemas_estrutura
                + response.red_flags
            )

            resultado = gerar_infografico_from_path(diagrama.arquivo.path, caminho_saida, sugestoes)

            if resultado:
                analise.imagem_infografico = f'relatorios/infografico_{diagrama.id}.png'
                analise.save()
                infografico_gerado = True
            else:
                erro_infografico = 'Nenhum resultado obtido na geração do infográfico.'
        except Exception as e:
            erro_infografico = str(e)

        return JsonResponse({
            'message': 'Análise realizada e salva com sucesso!' if created else 'Análise atualizada com sucesso!',
            'analise': {
                'id': analise.id,
                'indice_risco': analise.indice_risco,
                'classificacao': analise.classificacao,
                'tempo_processamento': analise.tempo_processamento,
                'infografico_gerado': infografico_gerado,
                'erro_infografico': erro_infografico
            }
        }, status=201 if created else 200)
    except Exception as e:
        return JsonResponse({'message': f'Erro ao processar análise: {str(e)}'}, status=500)


@csrf_exempt
def exportar_pdf(request, id):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
    
    # Check method
    if request.method != 'GET':
        return JsonResponse({'message': 'Método não permitido.'}, status=405)

    try:
        diagrama = Diagrama.objects.get(id=id)
    except Diagrama.DoesNotExist:
        return JsonResponse({'message': 'Diagrama não encontrado.'}, status=404)
        
    try:
        analise = AnaliseDiagrama.objects.get(diagrama=diagrama)
    except AnaliseDiagrama.DoesNotExist:
        return JsonResponse({'message': 'Análise não encontrada.'}, status=404)

    # Salvar em media/relatorios/
    relatorios_dir = os.path.join(settings.MEDIA_ROOT, 'relatorios')
    os.makedirs(relatorios_dir, exist_ok=True)
    pdf_path = os.path.join(relatorios_dir, f'analise_diagrama_{diagrama.id}.pdf')

    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=18,
                                 textColor=HexColor('#1e3a5f'), spaceAfter=20)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14,
                                   textColor=HexColor('#2d5986'), spaceBefore=15, spaceAfter=8)
    body_style = ParagraphStyle('CustomBody', parent=styles['Normal'], fontSize=10,
                                leading=14, spaceAfter=4)
    source_style = ParagraphStyle('SourceStyle', parent=styles['Normal'], fontSize=8,
                                  leading=10, spaceAfter=2, textColor=HexColor('#6b7280'))
    risk_style = ParagraphStyle('RiskStyle', parent=styles['Normal'], fontSize=24,
                                leading=30, alignment=1, spaceAfter=10)
    suggestion_style = ParagraphStyle('SuggestionStyle', parent=styles['Normal'], fontSize=9,
                                      leading=12, spaceAfter=4, textColor=HexColor('#4f46e5'),
                                      fontName='Helvetica-Oblique')

    elements = []

    # Titulo
    elements.append(Paragraph('Analise de Diagrama de Software', title_style))
    elements.append(Paragraph(f'Arquivo: {os.path.basename(diagrama.arquivo.name)}', body_style))
    elements.append(Paragraph(f'Data da analise: {analise.data_criacao.strftime("%d/%m/%Y %H:%M")}', body_style))
    elements.append(Paragraph(f'Tempo de processamento: {analise.tempo_processamento}s', body_style))
    elements.append(Spacer(1, 15))

    # Imagens: Diagrama Original e Infografico
    max_img_width = 12 * cm
    max_img_height = 12 * cm

    diagrama_path = diagrama.arquivo.path
    if os.path.exists(diagrama_path):
        elements.append(Paragraph('Diagrama Original', heading_style))
        img = Image(diagrama_path)
        img_ratio = img.imageWidth / img.imageHeight
        if img_ratio > 1:
            img.drawWidth = max_img_width
            img.drawHeight = max_img_width / img_ratio
        else:
            img.drawHeight = max_img_height
            img.drawWidth = max_img_height * img_ratio
        elements.append(img)
        elements.append(Spacer(1, 10))

    if analise.imagem_infografico:
        infografico_path = os.path.join(settings.MEDIA_ROOT, str(analise.imagem_infografico))
        if os.path.exists(infografico_path):
            elements.append(Paragraph('Diagrama com Sugestoes', heading_style))
            img = Image(infografico_path)
            img_ratio = img.imageWidth / img.imageHeight
            if img_ratio > 1:
                img.drawWidth = max_img_width
                img.drawHeight = max_img_width / img_ratio
            else:
                img.drawHeight = max_img_height
                img.drawWidth = max_img_height * img_ratio
            elements.append(img)
            elements.append(Spacer(1, 10))

    # Indice de Risco
    color_map = {'Baixo': '#10b981', 'Medio': '#f59e0b', 'Alto': '#f97316', 'Critico': '#ef4444'}
    risk_color = color_map.get(analise.classificacao, '#6b7280')
    elements.append(Paragraph('Indice de Risco Geral', heading_style))
    elements.append(Paragraph(f'<font color="{risk_color}" size="28"><b>{analise.indice_risco}</b></font>', risk_style))
    elements.append(Paragraph(f'<font color="{risk_color}"><b>Classificacao: {analise.classificacao}</b></font>',
                              ParagraphStyle('RiskClass', parent=body_style, alignment=1, fontSize=12)))
    elements.append(Spacer(1, 10))

    # Secoes
    sections = [
        ('Erros de Coerencia & Lacunas', analise.erros_coerencia,
         'Sugestao: Verifique fluxos desconectados, dependencias circulares e componentes orfaos.'),
        ('Riscos de Design Identificados', analise.riscos_identificados,
         'Sugestao: Reduza acoplamento, elimine pontos unicos de falha e adicione camadas de seguranca.'),
        ('Problemas de Estrutura', analise.problemas_estrutura,
         'Sugestao: Revise a notacao, adicione legendas e nomeie componentes de forma clara.'),
        ('Red Flags Criticas', analise.red_flags,
         'Recomendacao: Corrija violacoes SOLID, anti-patterns e falhas de seguranca antes de implementar.'),
    ]

    for title, items, sugestao in sections:
        elements.append(Paragraph(f'{title} ({len(items)})', heading_style))
        if items:
            for item in items:
                if isinstance(item, dict):
                    titulo = item.get("titulo", item.get("texto", str(item)))
                    elements.append(Paragraph(f'<b>&bull; {titulo}</b>', body_style))
                    fundamentacao = item.get("fundamentacao", "")
                    if fundamentacao:
                        elements.append(Paragraph(f'    {fundamentacao}', body_style))
                    fontes = item.get("fontes", [])
                    for fonte in fontes:
                        filename = fonte.get("filename", "")
                        page = fonte.get("page_number", "")
                        page_info = f", Pag. {page}" if page else ""
                        elements.append(Paragraph(f'    Fonte: {filename}{page_info}', source_style))
                else:
                    text = str(item)
                    elements.append(Paragraph(f'&bull; {text}', body_style))
        else:
            elements.append(Paragraph('Nenhum item identificado.', body_style))
        elements.append(Paragraph(sugestao, suggestion_style))
        elements.append(Spacer(1, 8))

    doc.build(elements)

    return FileResponse(open(pdf_path, 'rb'), as_attachment=True,
                        filename=f'analise_diagrama_{diagrama.id}.pdf')
