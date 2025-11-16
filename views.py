# seu_app/views.py
# (ESTE É O ARQUIVO COMPLETO E CORRIGIDO)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, authenticate, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

# --- IMPORTS DE BD E LÓGICA ---
from django.db.models import Q, OuterRef, Subquery, Sum, Count
from django.db.models.functions import TruncMonth
from dateutil.relativedelta import relativedelta 
from django.contrib import messages # <--- IMPORTANTE ADICIONADO
from django.views.decorators.http import require_POST # <--- IMPORTANTE ADICIONADO

# --- IMPORTS DOS MODELOS E FORMS (COM NOVAS ADIÇÕES) ---
# Adicionado Material, Comunicado
from .models import PerfilAluno, CodigoResetSenha, Curso, Matricula, Turma, Material, Comunicado
# Adicionado TurmaForm
from .forms import CursoForm, TurmaForm

import random, string

from django.views.decorators.http import require_http_methods

# --- Decorators ---

def staff_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if not request.user.is_staff:
            return redirect('minha_turma')
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

# --- Views Públicas ---

def index(request):
    return render(request, 'index.html')

def cursos(request):
    cursos_ativos = Curso.objects.filter(ativo=True).order_by('nome')
    context = {'lista_de_cursos': cursos_ativos}
    return render(request, 'cursos.html', context)

def sobrenos(request):
    return render(request, 'sobrenos.html')

# --- Matrícula P1 ---

def matricula(request):
    if request.method == 'POST':
        request.session['p1_data'] = {
            'curso': request.POST.get('curso'),
            'horario': request.POST.get('horario_preferido'),
            'dias': request.POST.getlist('dias'),
            'nivel': request.POST.get('nivel_ingles'),
            'objetivo': request.POST.get('objetivo'),
        }
        return redirect('matricula_p2')

    cursos_ativos = Curso.objects.filter(ativo=True).order_by('nome')
    return render(request, 'matricula.html', {'lista_de_cursos': cursos_ativos})

def matricula_finalizacao(request):
    return render(request, 'matricula-finalizacao.html')

# --- Login ---

def login(request):
    error_message = None
    if request.method == "POST":
        email_form = request.POST.get('email')
        password_form = request.POST.get('password')
        try:
            user_by_email = User.objects.get(email__iexact=email_form)
            username_real = user_by_email.username
            user = authenticate(request, username=username_real, password=password_form)
        except User.DoesNotExist:
            user = authenticate(request, username=email_form, password=password_form)
        except Exception:
            user = None

        if user is not None:
            auth_login(request, user)
            if user.is_staff or user.is_superuser:
                return redirect('admin')
            else:
                return redirect('minha_turma')
        else:
            error_message = "Email ou senha inválidos. Tente novamente."

    context = {'error': error_message}
    return render(request, 'login.html', context)

# --- Matrícula P2 (Auto-cadastro + Perfil + Matricula) ---

def matricula_p2(request):
    error_message = None

    p1_data = request.session.get('p1_data')
    if not p1_data:
        return redirect('matricula')

    if request.method == 'POST':
        # Dados pessoais
        nome = request.POST.get('nome')
        email = request.POST.get('email')
        telefone = request.POST.get('telefone') # <-- CORRIGIDO (estava request.GET)
        nascimento = request.POST.get('nascimento')
        cpf = request.POST.get('cpf')
        # Endereço
        cep = request.POST.get('cep')
        logradouro = request.POST.get('logradouro')
        numero = request.POST.get('numero')
        complemento = request.POST.get('complemento')
        bairro = request.POST.get('bairro')
        cidade = request.POST.get('cidade')
        estado = request.POST.get('estado')
        # Senhas
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        # Validações
        required_fields = [nome, email, telefone, nascimento, cpf, cep, logradouro, numero, bairro, cidade, estado, password, password_confirm]
        if not all(required_fields):
            error_message = "Por favor, preencha todos os campos obrigatórios (*)."
        elif password != password_confirm:
            error_message = "As senhas não coincidem."
        elif len(password) < 8:
            error_message = "A senha deve ter no mínimo 8 caracteres."
        elif User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            error_message = "Este e-mail (login) já está em uso."
        elif PerfilAluno.objects.filter(cpf=cpf).exists():
            error_message = "Este CPF já foi cadastrado."

        if error_message is None:
            try:
                with transaction.atomic():
                    partes_nome = nome.split(' ', 1)
                    first_name = partes_nome[0]
                    last_name = partes_nome[1] if len(partes_nome) > 1 else ''
                    email_normalizado = email.lower()

                    user = User.objects.create_user(
                        username=email_normalizado, email=email_normalizado, password=password,
                        first_name=first_name, last_name=last_name, is_staff=False
                    )

                    PerfilAluno.objects.create(
                        user=user,
                        cpf=cpf,
                        telefone=telefone,
                        data_nascimento=nascimento,
                        cep=cep,
                        logradouro=logradouro,
                        numero=numero,
                        complemento=complemento,
                        bairro=bairro,
                        cidade=cidade,
                        estado=estado,
                        curso_desejado=p1_data.get('curso'),
                        horario_preferido=p1_data.get('horario'),
                        dias_disponiveis=", ".join(p1_data.get('dias', [])),
                        nivel_ingles=p1_data.get('nivel'),
                        objetivo=p1_data.get('objetivo')
                    )

                    curso_obj = None
                    curso_nome_p1 = (p1_data.get('curso') or '').strip()
                    if curso_nome_p1:
                        curso_obj = Curso.objects.filter(nome__iexact=curso_nome_p1, ativo=True).first()
                        if not curso_obj:
                            try:
                                curso_obj = Curso.objects.create(nome=curso_nome_p1, preco_mes=0, ativo=True) 
                            except Exception:
                                curso_obj = None

                    if curso_obj:
                        Matricula.objects.get_or_create(aluno=user, curso=curso_obj) 

                    auth_login(request, user)

                    # E-mails (aluno + escola)
                    try:
                        assunto_aluno = "Seu voo está pronto! Bem-vindo(a) à High Flight!"
                        mensagem_aluno = f"""
Olá, {first_name}!

Seu voo para a fluência decolou! Estamos muito felizes em ter você a bordo.

Sua conta foi criada com sucesso. Seus dados de acesso são:
Login: {email_normalizado}
Senha: (a senha que você acabou de criar)

Nossa equipe de bordo entrará em contato para finalizar os detalhes da sua matrícula e te alocar na turma perfeita.

Enquanto isso, você já pode acessar seu portal do aluno: http://127.0.0.1:8000/minha-turma/

Atenciosamente,
Equipe High Flight
"""
                        send_mail(assunto_aluno, mensagem_aluno, settings.DEFAULT_FROM_EMAIL, [email_normalizado], fail_silently=False)

                        assunto_escola = f"Nova Pré-Matrícula Recebida - {nome}"
                        mensagem_escola = f"""
Uma nova pré-matrícula foi realizada no site.
 
DADOS PESSOAIS:
Aluno: {nome}
Email: {email_normalizado}
Telefone: {telefone}
CPF: {cpf}
Data de Nasc.: {nascimento}
 
ENDEREÇO:
Rua: {logradouro}, Nº {numero}
Complemento: {complemento}
Bairro: {bairro}
Cidade/UF: {cidade} - {estado}
CEP: {cep}
 
DADOS DO CURSO (P1):
Curso: {p1_data.get('curso')}
Horário: {p1_data.get('horario')}
Dias: {", ".join(p1_data.get('dias', []))}
Nível: {p1_data.get('nivel')}
Objetivo: {p1_data.get('objetivo')}

O usuário já foi criado no sistema e a matrícula foi registrada (pendente).
Próximo passo: Entrar em contato com o aluno para finalizar o processo.
"""
                        lista_emails_escola = ['eduardocarzzonicardoso@gmail.com', 'highflight@gmail.com']
                        send_mail(assunto_escola, mensagem_escola, settings.DEFAULT_FROM_EMAIL, lista_emails_escola, fail_silently=False)
                    except Exception as e:
                        print(f"ERRO AO ENVIAR E-MAIL DE MATRÍCULA: {e}")

                    if 'p1_data' in request.session:
                        del request.session['p1_data']
                    return redirect('matricula_finalizacao')

            except Exception as e:
                error_message = f"Ocorreu um erro inesperado: {e}"

    context = {'error': error_message}
    return render(request, 'matricula-p2.html', context)

# --- Recuperação de senha ---

def recuperarsenha(request):
    context = {}
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email__iexact=email)

            codigo_texto = ''.join(random.choices(string.digits, k=6))

            codigo_reset, created = CodigoResetSenha.objects.get_or_create(user=user)
            codigo_reset.codigo = codigo_texto
            codigo_reset.criado_em = timezone.now()
            codigo_reset.save()

            try:
                assunto = "Seu código de recuperação de senha - High Flight"
                mensagem = f"""
Olá, {user.first_name}!

Recebemos uma solicitação para redefinir a senha da sua conta.
Use o código de 6 dígitos abaixo para continuar.

Seu código é: {codigo_texto}

Este código é válido por 5 minutos.
Se você não solicitou esta alteração, por favor, ignore este e-mail.
"""
                send_mail(assunto, mensagem, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)

                request.session['email_reset'] = user.email
                return redirect('validar_codigo')

            except Exception as e:
                print(f"ERRO AO ENVIAR EMAIL DE RESET: {e}")
                context['error'] = "Não foi possível enviar o e-mail. Tente novamente."

        except User.DoesNotExist:
            context['error'] = "Nenhum usuário encontrado com este e-mail."
        except Exception as e:
            context['error'] = f"Ocorreu um erro: {e}"

    return render(request, 'recuperarsenha.html', context)

def validar_codigo(request):
    email_reset = request.session.get('email_reset')
    if not email_reset:
        return redirect('recuperarsenha')

    context = {}
    if request.method == 'POST':
        codigo_digitado = request.POST.get('codigo')
        try:
            user = User.objects.get(email__iexact=email_reset)
            codigo_obj = CodigoResetSenha.objects.get(user=user, codigo=codigo_digitado)

            if codigo_obj.esta_expirado():
                context['error'] = "Código expirado. Por favor, solicite um novo."
            else:
                request.session['user_id_reset'] = user.id
                codigo_obj.delete()
                return redirect('redefinir_senha')

        except CodigoResetSenha.DoesNotExist:
            context['error'] = "Código inválido. Tente novamente."
        except User.DoesNotExist:
            context['error'] = "Erro de usuário. Tente novamente."
        except Exception as e:
            context['error'] = f"Ocorreu um erro: {e}"

    return render(request, 'validar-codigo.html', context)

def redefinir_senha(request):
    user_id_reset = request.session.get('user_id_reset')
    if not user_id_reset:
        return redirect('login')

    context = {}
    if request.method == 'POST':
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        if password != password_confirm:
            context['error'] = "As senhas não coincidem."
        elif len(password) < 8:
            context['error'] = "A senha deve ter no mínimo 8 caracteres."
        else:
            try:
                user = User.objects.get(id=user_id_reset)
                user.set_password(password)
                user.save()

                del request.session['user_id_reset']
                if 'email_reset' in request.session:
                    del request.session['email_reset']

                auth_login(request, user)
                return redirect('minha_turma')

            except User.DoesNotExist:
                context['error'] = "Usuário não encontrado."
            except Exception as e:
                context['error'] = f"Ocorreu um erro: {e}"

    return render(request, 'redefinir-senha.html', context)


# --- Área do Admin ---

@login_required
@staff_required
def admin_view(request):
    hoje = timezone.now()
    
    # --- 1. CÁLCULO DOS CARDS ---
    inicio_mes_atual = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    inicio_mes_anterior = inicio_mes_atual - relativedelta(months=1)

    def variacao_percentual(atual, anterior):
        if anterior == 0:
            return 100.0 if atual > 0 else 0.0
        return round(((atual - anterior) / anterior) * 100.0, 1)

    # Card: Total de Alunos (não-staff)
    total_alunos = User.objects.filter(is_staff=False).count()
    novos_alunos_atual = User.objects.filter(is_staff=False, date_joined__gte=inicio_mes_atual).count()
    novos_alunos_anterior = User.objects.filter(is_staff=False, date_joined__gte=inicio_mes_anterior, date_joined__lt=inicio_mes_atual).count()
    variacao_alunos = variacao_percentual(novos_alunos_atual, novos_alunos_anterior)

    # Card: Matrículas Ativas
    matriculas_ativas_obj = Matricula.objects.filter(status=Matricula.Status.ATIVA)
    matriculas_ativas = matriculas_ativas_obj.count()
    novas_matriculas_atual = matriculas_ativas_obj.filter(data_matricula__gte=inicio_mes_atual).count()
    novas_matriculas_anterior = matriculas_ativas_obj.filter(data_matricula__gte=inicio_mes_anterior, data_matricula__lt=inicio_mes_atual).count()
    variacao_matriculas = variacao_percentual(novas_matriculas_atual, novas_matriculas_anterior)

    # Card: Receita Mensal
    receita_mes_atual_obj = matriculas_ativas_obj.aggregate(total=Sum('curso__preco_mes'))
    receita_mes_atual = receita_mes_atual_obj['total'] or 0

    # Variação da Receita
    receita_novas_mes_anterior_obj = Matricula.objects.filter(
        status=Matricula.Status.ATIVA, 
        data_matricula__gte=inicio_mes_anterior, 
        data_matricula__lt=inicio_mes_atual
    ).aggregate(total=Sum('curso__preco_mes'))
    receita_novas_mes_anterior = receita_novas_mes_anterior_obj['total'] or 0
    
    receita_novas_mes_atual_obj = Matricula.objects.filter(
        status=Matricula.Status.ATIVA, 
        data_matricula__gte=inicio_mes_atual
    ).aggregate(total=Sum('curso__preco_mes'))
    receita_novas_mes_atual = receita_novas_mes_atual_obj['total'] or 0
    variacao_receita = variacao_percentual(receita_novas_mes_atual, receita_novas_mes_anterior)

    # --- 2. DADOS PARA OS GRÁFICOS ---
    labels_meses = []
    data_inicio_grafico = (hoje - relativedelta(months=5)).replace(day=1)
    for i in range(6):
        try:
            import locale
            locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
        except:
            pass
        mes = (data_inicio_grafico + relativedelta(months=i)).strftime("%b/%Y")
        labels_meses.append(mes.capitalize()) 

    dados_db = (
        Matricula.objects
        .filter(data_matricula__gte=data_inicio_grafico)
        .annotate(mes=TruncMonth('data_matricula'))
        .values('mes')
        .annotate(
            total_matriculas=Count('id'),
            total_receita=Sum('curso__preco_mes')
        )
        .order_by('mes')
    )

    mapa_dados = {
        item['mes'].strftime("%b/%Y").capitalize(): {
            'matriculas': item['total_matriculas'],
            'receita': float(item['total_receita'] or 0)
        }
        for item in dados_db
    }
    dados_grafico_matriculas = [mapa_dados.get(label, {}).get('matriculas', 0) for label in labels_meses]
    dados_grafico_receita = [mapa_dados.get(label, {}).get('receita', 0) for label in labels_meses]

    # --- 3. CONTEXTO ---
    context = {
        'total_alunos': total_alunos,
        'variacao_alunos': variacao_alunos,
        'matriculas_ativas': matriculas_ativas,
        'variacao_matriculas': variacao_matriculas,
        'receita_mensal': receita_mes_atual,
        'variacao_receita': variacao_receita,
        'chart_labels': labels_meses,
        'chart_data_matriculas': dados_grafico_matriculas,
        'chart_data_receita': dados_grafico_receita,
    }
    return render(request, 'admin.html', context)


@login_required
@staff_required
def admin_matriculas_view(request):
    recentes = (
        Matricula.objects
        .select_related('aluno', 'curso')
        .order_by('-data_matricula')[:20]
    )
    ultima_matricula = (
        Matricula.objects
        .filter(aluno=OuterRef('user'))
        .order_by('-data_matricula')
    )
    lista_de_matriculas = (
        PerfilAluno.objects
        .select_related('user')
        .annotate(
            m_status=Subquery(ultima_matricula.values('status')[:1]),
            m_data=Subquery(ultima_matricula.values('data_matricula')[:1]),
        )
        .order_by('-id')
    )
    status_labels = dict(Matricula.Status.choices)
    for p in lista_de_matriculas:
        if p.m_status:
            p.status_display = status_labels.get(p.m_status, p.m_status.title())
            p.status_slug = p.m_status.lower()
        else:
            p.status_display = "Sem matrícula"
            p.status_slug = "sem-matricula"
        p.matricula_data = p.m_data
    context = {
        'recentes': recentes,
        'lista_de_matriculas': lista_de_matriculas,
    }
    return render(request, 'admin-matriculas.html', context)


# --- CRUD de Cursos (mantido da Views 1) ---

@login_required
@staff_required
def admin_cursos_view(request):
    cursos = Curso.objects.all().order_by('nome')
    context = {'lista_de_cursos': cursos}
    return render(request, 'admin-cursos.html', context)

@login_required
@staff_required
def admin_curso_add(request):
    if request.method == 'POST':
        form = CursoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('admin_cursos')
    else:
        form = CursoForm()
    context = {'form': form, 'page_title': 'Adicionar Novo Curso'}
    return render(request, 'admin-curso-form.html', context)

@login_required
@staff_required
def admin_curso_edit(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)
    if request.method == 'POST':
        form = CursoForm(request.POST, request.FILES, instance=curso)
        if form.is_valid():
            clear_image = request.POST.get('capa_curso-clear')
            if clear_image and curso.capa_curso:
                try:
                    curso.capa_curso.delete(save=False)
                except Exception as e:
                    print(f"AVISO: Falha ao deletar arquivo físico, permissão: {e}")
                form.instance.capa_curso = None
            form.save()
            return redirect('admin_cursos')
    else:
        form = CursoForm(instance=curso)
    context = {'form': form, 'page_title': f'Editando: {curso.nome}'}
    return render(request, 'admin-curso-form.html', context)

@login_required
@staff_required
def admin_curso_delete(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id)
    curso.delete()
    return redirect('admin_cursos')


# --- Área do aluno / Logout ---

@login_required
def minha_turma(request):
    if request.user.is_staff:
        return redirect('admin')

    # Busca turmas onde o usuário está no campo "alunos"
    turmas_do_aluno = request.user.turmas_onde_esta_matriculado.all().prefetch_related(
        'curso', 
        'responsavel', 
        'materiais',
        'comunicados'
    ).order_by('nome')

    context = {
        'turmas': turmas_do_aluno
    }
    
    return render(request, 'minha-turma.html', context)

def logout_view(request):
    auth_logout(request)
    return redirect('index')


@login_required
@staff_required
@require_http_methods(["GET", "POST"])
def admin_matricula_edit(request, user_id):
    # Garante PerfilAluno e (opcional) Matrícula
    aluno_user = get_object_or_404(User, id=user_id)
    perfil, _ = PerfilAluno.objects.get_or_create(user=aluno_user)
    # Se houver várias matrículas, aqui pegamos a mais recente; ajuste se quiser outra regra
    matricula = Matricula.objects.filter(aluno=aluno_user).order_by('-data_matricula').first()

    if request.method == 'POST':
        # Dados básicos do usuário
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip()

        # Perfil (dados pessoais)
        telefone   = request.POST.get('telefone', '').strip()
        cpf        = request.POST.get('cpf', '').strip()
        nascimento = request.POST.get('data_nascimento', '').strip()

        # Endereço
        cep         = request.POST.get('cep', '').strip()
        logradouro  = request.POST.get('logradouro', '').strip()
        numero      = request.POST.get('numero', '').strip()
        complemento = request.POST.get('complemento', '').strip()
        bairro      = request.POST.get('bairro', '').strip()
        cidade      = request.POST.get('cidade', '').strip()
        estado      = request.POST.get('estado', '').strip()

        # Preferências (P1)
        curso_desejado     = request.POST.get('curso_desejado', '').strip()
        horario_preferido  = request.POST.get('horario_preferido', '').strip()
        dias_disponiveis   = request.POST.get('dias_disponiveis', '').strip()
        nivel_ingles       = request.POST.get('nivel_ingles', '').strip()
        objetivo           = request.POST.get('objetivo', '').strip()

        # Status da matrícula (dropdown)
        novo_status = request.POST.get('status', '').strip()

        error = None
        if not first_name or not email:
            error = "Nome e e-mail são obrigatórios."
        elif User.objects.filter(email__iexact=email).exclude(id=aluno_user.id).exists():
            error = "Já existe outro usuário com este e-mail."

        if error:
            return render(request, 'admin-matricula-edit.html', {
                'aluno_user': aluno_user,
                'perfil': perfil,
                'matricula': matricula,
                'error': error,
                'StatusChoices': Matricula.Status.choices,
            })

        aluno_user.first_name = first_name
        aluno_user.last_name  = last_name
        aluno_user.email      = email
        aluno_user.username   = email.lower() or aluno_user.username
        aluno_user.save()

        perfil.telefone        = telefone
        perfil.cpf             = cpf or perfil.cpf
        perfil.data_nascimento = nascimento

        perfil.cep         = cep
        perfil.logradouro  = logradouro
        perfil.numero      = numero
        perfil.complemento = complemento
        perfil.bairro      = bairro
        perfil.cidade      = cidade
        perfil.estado      = estado

        perfil.curso_desejado    = curso_desejado
        perfil.horario_preferido = horario_preferido
        perfil.dias_disponiveis  = dias_disponiveis
        perfil.nivel_ingles      = nivel_ingles
        perfil.objetivo          = objetivo
        perfil.save()

        if matricula and novo_status in dict(Matricula.Status.choices):
            matricula.status = novo_status
            matricula.save()

        return redirect('admin_matriculas')

    return render(request, 'admin-matricula-edit.html', {
        'aluno_user': aluno_user,
        'perfil': perfil,
        'matricula': matricula,
        'StatusChoices': Matricula.Status.choices,
    })

@login_required
@staff_required
def admin_turmas_view(request):
    """
    View para LISTAR todas as turmas.
    """
    turmas = Turma.objects.select_related('curso', 'responsavel').all().order_by('curso__nome', 'nome')
    context = {'lista_de_turmas': turmas}
    return render(request, 'admin-turmas.html', context)

@login_required
@staff_required
def admin_turma_delete(request, turma_id):
    """
    View para DELETAR uma turma.
    """
    turma = get_object_or_404(Turma, id=turma_id)
    turma.delete()
    messages.success(request, f"Turma '{turma.nome}' excluída com sucesso.")
    return redirect('admin_turmas')

@login_required
@staff_required
def admin_turma_form_view(request, turma_id=None):
    """
    View unificada para ADICIONAR (se turma_id=None) 
    ou EDITAR (se turma_id for passado).
    """
    if turma_id:
        turma = get_object_or_404(Turma, id=turma_id)
        page_title = f"Editar Turma: {turma.nome}"
    else:
        turma = None
        page_title = "Adicionar Nova Turma"

    if request.method == 'POST':
        form = TurmaForm(request.POST, instance=turma)
        if form.is_valid():
            nova_turma = form.save()
            messages.success(request, "Detalhes da turma salvos com sucesso!")
            return redirect('admin_turma_edit', turma_id=nova_turma.id)
    else:
        form = TurmaForm(instance=turma)

    alunos_na_turma = []
    matriculas_para_adicionar = []
    
    if turma:
        alunos_na_turma = turma.alunos.all().order_by('first_name', 'last_name')
        
        alunos_ja_na_turma_ids = alunos_na_turma.values_list('id', flat=True)
        
        matriculas_para_adicionar = Matricula.objects.filter(
            curso=turma.curso,
            status=Matricula.Status.ATIVA
        ).exclude(
            aluno__id__in=alunos_ja_na_turma_ids
        ).select_related('aluno')

    context = {
        'page_title': page_title,
        'form': form,
        'turma': turma,
        'alunos_na_turma': alunos_na_turma,
        'matriculas_para_adicionar': matriculas_para_adicionar,
    }
    return render(request, 'admin-turma-form.html', context) 

@login_required
@staff_required
@require_POST
def admin_turma_add_aluno(request, turma_id):
    turma = get_object_or_404(Turma, id=turma_id)
    aluno_id = request.POST.get('aluno_para_adicionar')

    if not aluno_id:
        messages.error(request, "Você não selecionou um aluno.")
        return redirect('admin_turma_edit', turma_id=turma_id)

    aluno = get_object_or_404(User, id=aluno_id)
    
    turma.alunos.add(aluno)
    messages.success(request, f"{aluno.get_full_name()} foi adicionado(a) à turma!")
    
    return redirect('admin_turma_edit', turma_id=turma_id)

@login_required
@staff_required
@require_POST 
def admin_turma_remove_aluno(request, turma_id, aluno_id):
    turma = get_object_or_404(Turma, id=turma_id)
    aluno = get_object_or_404(User, id=aluno_id)

    turma.alunos.remove(aluno)
    messages.success(request, f"{aluno.get_full_name()} foi removido(a) da turma.")

    return redirect('admin_turma_edit', turma_id=turma_id)

@login_required
@staff_required
@require_POST
def admin_enviar_comunicado(request, turma_id):
    turma = get_object_or_404(Turma, id=turma_id)
    
    titulo = request.POST.get('titulo')
    mensagem = request.POST.get('mensagem')

    if not titulo or not mensagem:
        messages.error(request, "Título e Mensagem são obrigatórios para enviar um comunicado.")
        return redirect('admin_turma_edit', turma_id=turma_id)

    Comunicado.objects.create(
        turma=turma,
        autor=request.user,
        titulo=titulo,
        mensagem=mensagem
    )
    
    messages.success(request, "Aviso enviado para a turma!")
    return redirect('admin_turma_edit', turma_id=turma_id)

@login_required
@staff_required
@require_POST
def admin_adicionar_material(request, turma_id):
    turma = get_object_or_404(Turma, id=turma_id)
    
    titulo = request.POST.get('titulo')
    arquivo = request.FILES.get('arquivo')
    link = request.POST.get('link')

    if not titulo or (not arquivo and not link):
        messages.error(request, "Título e (Arquivo ou Link) são obrigatórios para adicionar material.")
        return redirect('admin_turma_edit', turma_id=turma_id)

    Material.objects.create(
        turma=turma,
        autor=request.user,
        titulo=titulo,
        arquivo=arquivo,
        link=link
    )
    
    messages.success(request, "Material adicionado à turma!")
    return redirect('admin_turma_edit', turma_id=turma_id)