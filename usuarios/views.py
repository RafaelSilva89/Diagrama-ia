import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import Projeto, Diagrama

def _get_user(request, data=None):
    """Helper para obter o usuário do Gateway através do Header X-User-Id, body json ou session (fallback)"""
    user_id = request.headers.get('X-User-Id')
    
    if not user_id and data:
        user_id = data.get('user_id')
        
    if user_id:
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
            
    if request.user and request.user.is_authenticated:
        return request.user
        
    return None

@csrf_exempt
def cadastro(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            senha = data.get('senha')
            confirmar_senha = data.get('confirmar_senha', senha) # fallback

            if not username or not senha:
                return JsonResponse({'message': 'Username e senha são obrigatórios.'}, status=400)

            if senha != confirmar_senha:
                return JsonResponse({'message': 'Senha e confirmar senha não são iguais.'}, status=400)

            if len(senha) < 6:
                return JsonResponse({'message': 'Sua senha deve ter pelo menos 6 caracteres.'}, status=400)

            if User.objects.filter(username=username).exists():
                return JsonResponse({'message': 'Já existe um usuário com esse username.'}, status=400)

            user = User.objects.create_user(
                username=username,
                password=senha
            )

            return JsonResponse({'message': 'Usuário criado com sucesso.', 'user_id': user.id}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'message': 'JSON inválido.'}, status=400)
    return JsonResponse({'message': 'Método não permitido.'}, status=405)

@csrf_exempt
def login(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            senha = data.get('senha')

            user = authenticate(username=username, password=senha)
            if user is not None:
                return JsonResponse({'message': 'Login realizado com sucesso.', 'user_id': user.id}, status=200)
            else:
                return JsonResponse({'message': 'Usuário ou senha inválidos.'}, status=401)
        except json.JSONDecodeError:
            return JsonResponse({'message': 'JSON inválido.'}, status=400)
    return JsonResponse({'message': 'Método não permitido.'}, status=405)

@csrf_exempt
def sair(request):
    return JsonResponse({'message': 'Logout concluído. O API Gateway deve invalidar o token.'}, status=200)

@csrf_exempt
def admin_login_redirect(request):
    return JsonResponse({'message': 'Admin login API route.'}, status=403)

@csrf_exempt
def projetos(request):
    if request.method == 'GET':
        user = _get_user(request)
        if not user:
            return JsonResponse({'message': 'Usuário não autenticado ou X-User-Id não fornecido nos headers.'}, status=401)
            
        projetos_list = Projeto.objects.filter(user=user)
        dados_projetos = [
            {'id': p.id, 'nome': p.nome, 'data_criacao': p.data_criacao.strftime('%Y-%m-%dT%H:%M:%S')}
            for p in projetos_list
        ]
        return JsonResponse({'projetos': dados_projetos, 'total': len(dados_projetos)}, status=200)
        
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            nome = data.get('nome')
            
            if not nome:
                return JsonResponse({'message': 'O campo nome é obrigatório.'}, status=400)
                
            user = _get_user(request, data)
            if not user:
                return JsonResponse({'message': 'Usuário não autenticado ou X-User-Id não fornecido.'}, status=401)
                
            projeto = Projeto.objects.create(nome=nome, user=user)
            return JsonResponse({'message': 'Projeto criado com sucesso!', 'projeto_id': projeto.id}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'message': 'JSON inválido.'}, status=400)
            
    return JsonResponse({'message': 'Método não permitido.'}, status=405)

@csrf_exempt
def projeto(request, id):
    try:
        projeto = Projeto.objects.get(id=id)
    except Projeto.DoesNotExist:
        return JsonResponse({'message': 'Projeto não encontrado.'}, status=404)
        
    if request.method == 'GET':
        diagramas = Diagrama.objects.filter(projeto=projeto)
        dados_diagramas = [
            {'id': d.id, 'arquivo': d.arquivo.name, 'data_upload': d.data_upload.strftime('%Y-%m-%dT%H:%M:%S')}
            for d in diagramas
        ]
        dados_projeto = {'id': projeto.id, 'nome': projeto.nome, 'user_id': projeto.user.id}
        
        return JsonResponse({'projeto': dados_projeto, 'diagramas': dados_diagramas}, status=200)
        
    elif request.method == 'POST':
        # Nota: Upload de arquivos via web requer form-data (postman). Não json body puro.
        arquivo = request.FILES.get('diagrama')
        if not arquivo:
            return JsonResponse({'message': 'O upload do arquivo (campo diagrama) via form-data é obrigatório.'}, status=400)
            
        diagrama = Diagrama.objects.create(projeto=projeto, arquivo=arquivo)
        return JsonResponse({'message': 'Diagrama gravado com sucesso.', 'diagrama_id': diagrama.id}, status=201)
        
    return JsonResponse({'message': 'Método não permitido.'}, status=405)

@csrf_exempt
def deletar_diagrama(request, id):
    if request.method in ['DELETE', 'POST', 'GET']:
        try:
            diagrama = Diagrama.objects.get(id=id)
            diagrama.arquivo.delete()
            diagrama.delete()
            return JsonResponse({'message': 'Diagrama deletado com sucesso.'}, status=200)
        except Diagrama.DoesNotExist:
            return JsonResponse({'message': 'Diagrama não encontrado.'}, status=404)
            
    return JsonResponse({'message': 'Método não permitido.'}, status=405)
