# seu_app/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime

# ---------------------------
# PERFIL DO ALUNO
# ---------------------------
class PerfilAluno(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    cpf = models.CharField(max_length=14, unique=True)
    telefone = models.CharField(max_length=20)
    data_nascimento = models.CharField(max_length=10)

    # Endereço
    cep = models.CharField(max_length=9, blank=True, null=True)
    logradouro = models.CharField(max_length=200, blank=True, null=True)
    numero = models.CharField(max_length=20, blank=True, null=True)
    complemento = models.CharField(max_length=100, blank=True, null=True)
    bairro = models.CharField(max_length=100, blank=True, null=True)
    cidade = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=2, blank=True, null=True)

    # Preferências (P1)
    curso_desejado = models.CharField(max_length=100, blank=True, null=True)
    horario_preferido = models.CharField(max_length=100, blank=True, null=True)
    dias_disponiveis = models.CharField(max_length=200, blank=True, null=True)
    nivel_ingles = models.CharField(max_length=100, blank=True, null=True)
    objetivo = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.user.username


# ---------------------------
# CÓDIGO DE RESET DE SENHA
# ---------------------------
class CodigoResetSenha(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    codigo = models.CharField(max_length=6)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.codigo}"

    def esta_expirado(self):
        agora = timezone.now()
        cinco_minutos_atras = agora - datetime.timedelta(minutes=5)
        return self.criado_em < cinco_minutos_atras


# ---------------------------
# CURSO (CATÁLOGO)
# ---------------------------
class Curso(models.Model):
    CURSO_CHOICES = [
        ('presencial', 'Presencial'),
        ('online', 'Online'),
    ]
    TIPO_CHOICES = [
        ('turma', 'Turma'),
        ('executivo', 'Executivo'),
        ('vip', 'VIP'),
    ]

    nome = models.CharField(max_length=120, unique=True) 
    descricao = models.TextField(blank=True, null=True)
    capa_curso = models.ImageField(
        upload_to='cursos/capas/',
        blank=True,
        null=True,
        verbose_name='Capa do Curso'
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='turma')
    modalidade = models.CharField(max_length=20, choices=CURSO_CHOICES, default='presencial')

    # (Este é o campo que corrigimos)
    preco_mes = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

    @property
    def get_nome_completo(self):
        return f"{self.nome} {self.get_modalidade_display()}"


# ---------------------------
# MATRÍCULA (INSCRIÇÃO NO CURSO)
# ---------------------------
class Matricula(models.Model):
    class Status(models.TextChoices):
        ATIVA = "ATIVA", "Ativa"
        PENDENTE = "PENDENTE", "Pendente"
        CANCELADA = "CANCELADA", "Cancelada"

    aluno = models.ForeignKey(User, on_delete=models.CASCADE, related_name="matriculas")
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name="matriculas")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    data_matricula = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['aluno', 'curso'], name='unique_matricula_por_curso')
        ]

    def __str__(self):
        return f"{self.aluno} - {self.curso} ({self.status})"


# ================================================
# NOVOS MODELOS - TURMA, MATERIAL, COMUNICADO
# ================================================

class Turma(models.Model):
    """
    Representa uma turma específica de um curso.
    Ex: 'Turma A' do curso 'Inglês Básico'.
    """
    class Status(models.TextChoices):
        ABERTA = "ABERTA", "Inscrições Abertas"
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em Andamento"
        CONCLUIDA = "CONCLUIDA", "Concluída"

    nome = models.CharField(max_length=100, verbose_name="Nome da Turma")
    
    # Relação: A que curso esta turma pertence?
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name="turmas_do_curso")
    
    # Relação: Quem é o professor?
    responsavel = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        limit_choices_to={'is_staff': True}, # Só permite selecionar staff
        related_name="turmas_responsavel"
    )
    
    horario = models.CharField(max_length=100, blank=True, null=True, help_text="Ex: 19:00 - 20:30")
    dias = models.CharField(max_length=100, blank=True, null=True, help_text="Ex: Segundas e Quartas")
    data_inicio = models.DateField(blank=True, null=True)
    max_alunos = models.PositiveIntegerField(default=10)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ABERTA)

    # Relação: Quais alunos estão nesta turma?
    # Este é o campo "Alunos Associados".
    alunos = models.ManyToManyField(
        User,
        related_name="turmas_onde_esta_matriculado", # Usaremos isso na view 'minha_turma'
        blank=True
    )

    def __str__(self):
        return f"{self.nome} ({self.curso.nome})"

    @property
    def get_vagas_disponiveis(self):
        matriculas_contadas = self.alunos.count() # Simplesmente conta os alunos associados
        return self.max_alunos - matriculas_contadas


# Em seu models.py (substitua os modelos Material e Comunicado)

class Material(models.Model):
    """
    Material de apoio (PDF, link, etc.) para uma Turma.
    """
    turma = models.ForeignKey(Turma, on_delete=models.CASCADE, related_name="materiais")
    
    # --- CAMPO ADICIONADO ---
    # Para saber quem (qual admin/professor) enviou
    autor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        limit_choices_to={'is_staff': True}
    )
    
    titulo = models.CharField(max_length=150)
    descricao = models.TextField(blank=True, null=True)
    arquivo = models.FileField(upload_to='materiais/%Y/%m/', blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    
    def __str__(self):
        return self.titulo


class Comunicado(models.Model):
    """
    Um aviso ou comunicado do professor para a Turma.
    """
    turma = models.ForeignKey(Turma, on_delete=models.CASCADE, related_name="comunicados")
    
    # --- CAMPO ADICIONADO ---
    # Para saber quem (qual admin/professor) enviou
    autor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        limit_choices_to={'is_staff': True}
    )
    
    titulo = models.CharField(max_length=150)
    mensagem = models.TextField()
    data_publicacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_publicacao']

    def __str__(self):
        return self.titulo