from django.db import models
from usuarios.models import Diagrama


class AnaliseDiagrama(models.Model):
    diagrama = models.ForeignKey(Diagrama, on_delete=models.CASCADE, related_name='analises')
    indice_risco = models.IntegerField()
    classificacao = models.CharField(max_length=20)
    erros_coerencia = models.JSONField(default=list)
    riscos_identificados = models.JSONField(default=list)
    problemas_estrutura = models.JSONField(default=list)
    red_flags = models.JSONField(default=list)
    fontes_rag = models.JSONField(default=dict, blank=True)
    imagem_infografico = models.ImageField(upload_to='relatorios/', null=True, blank=True)
    tempo_processamento = models.IntegerField(default=0)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_criacao']

    def __str__(self):
        return f"Análise - {self.diagrama.arquivo.name} - {self.data_criacao.strftime('%d/%m/%Y %H:%M')}"
