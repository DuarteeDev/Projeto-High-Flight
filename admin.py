# seu_app/admin.py
from django.contrib import admin
from .models import PerfilAluno, CodigoResetSenha, Curso, Matricula, Turma, Material, Comunicado

# Modelos que já existiam
admin.site.register(PerfilAluno)
admin.site.register(CodigoResetSenha)
admin.site.register(Curso)
admin.site.register(Matricula)

class MaterialInline(admin.TabularInline):
    model = Material
    extra = 1

class ComunicadoInline(admin.TabularInline):
    model = Comunicado
    extra = 1

@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'curso', 'responsavel', 'dias', 'horario')
    list_filter = ('curso', 'responsavel')
    
    filter_horizontal = ('alunos',) 
    inlines = [MaterialInline, ComunicadoInline]

admin.site.register(Material)
admin.site.register(Comunicado)