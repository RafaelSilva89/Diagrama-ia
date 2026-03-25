from django.urls import reverse
from django.shortcuts import render, redirect
from django.contrib.messages import constants
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from .models import Projeto, Diagrama


def cadastro(request):
    if request.method == 'GET':
        return render(request, 'cadastro.html')
    elif request.method == 'POST':
        username = request.POST.get('username')
        senha = request.POST.get('senha')
        confirmar_senha = request.POST.get('confirmar_senha')

        if not senha == confirmar_senha:
            messages.add_message(request, constants.ERROR, 'Senha e confirmar senha não são iguais.')
            return redirect('cadastro')

        if len(senha) < 6:
            messages.add_message(request, constants.ERROR, 'Sua senha deve ter pelo meno 6 caracteres.')
            return redirect('cadastro')

        users = User.objects.filter(username=username)

        if users.exists():
            messages.add_message(request, constants.ERROR, 'Já existe um usuário com esse username.')
            return redirect('cadastro')

        User.objects.create_user(
            username=username,
            password=senha
        )

        return redirect('login')


def login(request):
    if request.method == 'GET':
        return render(request, 'login.html')
    elif request.method == 'POST':
        username = request.POST.get('username')
        senha = request.POST.get('senha')

        user = authenticate(username=username, password=senha)
        if user is not None:
            auth.login(request, user)
            return redirect('projetos')
        else:
            messages.add_message(request, constants.ERROR, 'Usuário ou senha inválidos.')
            return redirect('login')


@login_required
def projetos(request):
    if request.method == 'GET':
        projetos_list = Projeto.objects.filter(user=request.user)
        total = projetos_list.count()
        return render(request, 'projetos.html', {
            'projetos': projetos_list,
            'total': total,
        })
    elif request.method == 'POST':
        nome = request.POST.get('nome')
        Projeto.objects.create(nome=nome, user=request.user)
        messages.add_message(request, constants.SUCCESS, 'Projeto criado com sucesso!')
        return redirect('projetos')


@login_required
def sair(request):
    auth.logout(request)
    return redirect('login')


@login_required
def admin_login_redirect(request):
    auth.logout(request)
    return redirect('/admin/login/?next=/admin/')


@login_required
def projeto(request, id):
    projeto = Projeto.objects.get(id=id)
    if request.method == 'GET':
        diagramas = Diagrama.objects.filter(projeto=projeto)
        return render(request, 'projeto.html', {'projeto': projeto, 'diagramas': diagramas})
    elif request.method == 'POST':
        arquivo = request.FILES.get('diagrama')
        Diagrama.objects.create(projeto=projeto, arquivo=arquivo)
        return redirect(reverse('projeto', kwargs={'id': projeto.id}))


@login_required
def deletar_diagrama(request, id):
    diagrama = Diagrama.objects.get(id=id)
    projeto_id = diagrama.projeto.id
    diagrama.arquivo.delete()
    diagrama.delete()
    return redirect(reverse('projeto', kwargs={'id': projeto_id}))
