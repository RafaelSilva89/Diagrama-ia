from django.db import models
from django.contrib.auth.models import User


class Projeto(models.Model):
    nome = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome


class Diagrama(models.Model):
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE)
    arquivo = models.FileField(upload_to='diagramas/')
    data_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.arquivo.name
