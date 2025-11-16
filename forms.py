
from django import forms
from .models import Curso, Turma

class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = [
            'nome', 'descricao', 'capa_curso', 
            'tipo', 'modalidade', 'preco_mes', 'ativo'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'placeholder': 'Digite o título do curso...'}),
            'descricao': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Digite a descrição detalhada do curso...'}),
            'tipo': forms.Select(),
            'modalidade': forms.Select(),
            'preco_mes': forms.NumberInput(attrs={'placeholder': '0.00'}),
        }
        labels = {
            'nome': 'Título do Curso*',
            'descricao': 'Descrição*',
            'preco_mes': 'Valor*',
            'capa_curso': 'Capa do Curso',
            'tipo': 'Tipo de Curso',
            'modalidade': 'Modalidade',
            'ativo': 'Curso está ativo (aparecerá no site)',
        }

class TurmaForm(forms.ModelForm):
    data_inicio = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'input-field'
        }),
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        required=False
    )

    class Meta:
        model = Turma
        fields = [
            'curso', 'nome', 'responsavel', 
            'dias', 'horario', 'data_inicio', 
            'max_alunos'
        ]
        widgets = {
            'curso': forms.Select(attrs={'class': 'input-field'}),
            'nome': forms.TextInput(attrs={'placeholder': 'Ex: Turma de Sábado (Manhã)', 'class': 'input-field'}),
            'responsavel': forms.Select(attrs={'class': 'input-field'}),
            'dias': forms.TextInput(attrs={'placeholder': 'Ex: Segundas e Quartas', 'class': 'input-field'}),
            'horario': forms.TextInput(attrs={'placeholder': 'Ex: 19:00 - 20:30', 'class': 'input-field'}),
            'max_alunos': forms.NumberInput(attrs={'class': 'input-field'}),
        }
        labels = {
            'curso': 'Curso*',
            'nome': 'Nome da Turma*',
            'responsavel': 'Professor Responsável',
            'dias': 'Dias da Semana',
            'horario': 'Horário',
            'data_inicio': 'Data de Início',
            'max_alunos': 'Max. Alunos',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['curso'].queryset = Curso.objects.filter(ativo=True)