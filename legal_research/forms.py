from django import forms
from django.utils import timezone
from .models import LegalResearchQuery, ResearchSession
from cases.models import Case
from clients.models import Client
from documents.models import Document


class LegalResearchQueryForm(forms.ModelForm):
    """
    Form for creating and editing legal research queries.
    """
    class Meta:
        model = LegalResearchQuery
        fields = [
            'title', 'query', 'query_type', 'case', 'client', 'documents',
            'jurisdiction', 'practice_area', 'relevant_facts', 'specific_requirements'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter a descriptive title for your research query'
            }),
            'query': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe your legal research question in detail...'
            }),
            'query_type': forms.Select(attrs={'class': 'form-control'}),
            'case': forms.Select(attrs={'class': 'form-control'}),
            'client': forms.Select(attrs={'class': 'form-control'}),
            'documents': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'jurisdiction': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Federal, California, New York'
            }),
            'practice_area': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Corporate Law, Family Law, Criminal Law'
            }),
            'relevant_facts': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Provide relevant facts and context...'
            }),
            'specific_requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any specific requirements or constraints...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if request and hasattr(request, 'tenant'):
            tenant = request.tenant
            
            # Filter cases by tenant
            self.fields['case'].queryset = Case.objects.filter(
                tenant=tenant,
                deleted_at__isnull=True
            )
            self.fields['case'].required = False
            
            # Filter clients by tenant
            self.fields['client'].queryset = Client.objects.filter(
                tenant=tenant,
                deleted_at__isnull=True
            )
            self.fields['client'].required = False
            
            # Filter documents by tenant and user
            self.fields['documents'].queryset = Document.objects.filter(
                tenant=tenant,
                uploaded_by=request.user,
                deleted_at__isnull=True
            )
            self.fields['documents'].required = False
    
    def clean_query(self):
        """Validate the query field."""
        query = self.cleaned_data.get('query')
        if not query or len(query.strip()) < 10:
            raise forms.ValidationError(
                "Please provide a more detailed research query (minimum 10 characters)."
            )
        return query.strip()
    
    def clean_title(self):
        """Validate the title field."""
        title = self.cleaned_data.get('title')
        if not title or len(title.strip()) < 5:
            raise forms.ValidationError(
                "Title must be at least 5 characters long."
            )
        return title.strip()


class QuickResearchForm(forms.Form):
    """
    Quick form for rapid legal research queries.
    """
    query = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ask a legal research question...'
        }),
        help_text="Enter your legal research question"
    )
    query_type = forms.ChoiceField(
        choices=[
            ('case_law', 'Case Law'),
            ('statute', 'Statute'),
            ('legal_analysis', 'Legal Analysis'),
            ('document_review', 'Document Review'),
        ],
        initial='case_law',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    jurisdiction = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Jurisdiction (optional)'
        })
    )
    
    def clean_query(self):
        """Validate the query field."""
        query = self.cleaned_data.get('query')
        if not query or len(query.strip()) < 5:
            raise forms.ValidationError(
                "Please provide a more detailed question (minimum 5 characters)."
            )
        return query.strip()


class ResearchSessionForm(forms.ModelForm):
    """
    Form for creating and managing research sessions.
    """
    class Meta:
        model = ResearchSession
        fields = ['title', 'description', 'overall_objective', 'case', 'client']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter session title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Brief description of the research session'
            }),
            'overall_objective': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'What is the overall objective of this research session?'
            }),
            'case': forms.Select(attrs={'class': 'form-control'}),
            'client': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if request and hasattr(request, 'tenant'):
            tenant = request.tenant
            
            # Filter cases by tenant
            self.fields['case'].queryset = Case.objects.filter(
                tenant=tenant,
                deleted_at__isnull=True
            )
            self.fields['case'].required = False
            
            # Filter clients by tenant
            self.fields['client'].queryset = Client.objects.filter(
                tenant=tenant,
                deleted_at__isnull=True
            )
            self.fields['client'].required = False


class DocumentAnalysisForm(forms.Form):
    """
    Form for analyzing documents with AI.
    """
    documents = forms.ModelMultipleChoiceField(
        queryset=Document.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text="Select documents to analyze"
    )
    analysis_type = forms.ChoiceField(
        choices=[
            ('summary', 'Document Summary'),
            ('key_points', 'Key Points Extraction'),
            ('legal_issues', 'Legal Issues Identification'),
            ('risk_assessment', 'Risk Assessment'),
            ('contract_analysis', 'Contract Analysis'),
            ('evidence_review', 'Evidence Review'),
        ],
        initial='summary',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    specific_questions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Any specific questions about these documents?'
        })
    )
    
    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if request and hasattr(request, 'tenant'):
            tenant = request.tenant
            
            # Filter documents by tenant and user
            self.fields['documents'].queryset = Document.objects.filter(
                tenant=tenant,
                uploaded_by=request.user,
                deleted_at__isnull=True
            )
    
    def clean_documents(self):
        """Validate that at least one document is selected."""
        documents = self.cleaned_data.get('documents')
        if not documents:
            raise forms.ValidationError(
                "Please select at least one document to analyze."
            )
        return documents


class ResearchFeedbackForm(forms.ModelForm):
    """
    Form for collecting user feedback on research results.
    """
    class Meta:
        model = LegalResearchQuery
        fields = ['user_rating', 'user_feedback', 'is_helpful']
        widgets = {
            'user_rating': forms.RadioSelect(
                choices=[(i, f'{i} star{"s" if i > 1 else ""}') for i in range(1, 6)],
                attrs={'class': 'form-check-input'}
            ),
            'user_feedback': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Please provide feedback on the research result...'
            }),
            'is_helpful': forms.RadioSelect(
                choices=[(True, 'Helpful'), (False, 'Not Helpful')],
                attrs={'class': 'form-check-input'}
            ),
        }
    
    def clean_user_rating(self):
        """Validate the rating."""
        rating = self.cleaned_data.get('user_rating')
        if rating and rating < 1 or rating > 5:
            raise forms.ValidationError("Rating must be between 1 and 5.")
        return rating


class ResearchFilterForm(forms.Form):
    """
    Form for filtering research queries.
    """
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + LegalResearchQuery.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    query_type = forms.ChoiceField(
        choices=[('', 'All Types')] + LegalResearchQuery.QUERY_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    case = forms.ModelChoiceField(
        queryset=Case.objects.none(),
        required=False,
        empty_label="All Cases",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    client = forms.ModelChoiceField(
        queryset=Client.objects.none(),
        required=False,
        empty_label="All Clients",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if request and hasattr(request, 'tenant'):
            tenant = request.tenant
            
            # Filter cases and clients by tenant
            self.fields['case'].queryset = Case.objects.filter(
                tenant=tenant,
                deleted_at__isnull=True
            )
            self.fields['client'].queryset = Client.objects.filter(
                tenant=tenant,
                deleted_at__isnull=True
            )
