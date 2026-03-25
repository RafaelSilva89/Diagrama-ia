from django.urls import path
from . import views

urlpatterns = [
    path('cadastro/', views.cadastro, name='cadastro'),
    path('login/', views.login, name='login'),
    path('projetos/', views.projetos, name='projetos'),
    path('projeto/<int:id>', views.projeto, name='projeto'),
    path('logout/', views.sair, name='sair'),
    path('admin-redirect/', views.admin_login_redirect, name='admin_login_redirect'),
    path('deletar-diagrama/<int:id>', views.deletar_diagrama, name='deletar_diagrama'),
]
