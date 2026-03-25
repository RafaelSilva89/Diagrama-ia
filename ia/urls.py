from django.urls import path
from . import views

urlpatterns = [
    path('analise_diagrama/<int:id>', views.analise_diagrama, name='analise_diagrama'),
    path('processar_analise/<int:id>', views.processar_analise, name='processar_analise'),
    path('exportar_pdf/<int:id>', views.exportar_pdf, name='exportar_pdf'),
]
