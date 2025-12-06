import time
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.views.decorators.http import require_POST
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count
from django.utils import timezone
from django.core.paginator import Paginator
from decouple import config

from .models import LegalResearchQuery, ResearchSession, ResearchSource
from .forms import (
    LegalResearchQueryForm, QuickResearchForm, ResearchSessionForm,
    DocumentAnalysisForm, ResearchFeedbackForm, ResearchFilterForm
)
from .services import GeminiAIService, DocumentAnalyzer


class LegalResearchQueryListView(LoginRequiredMixin, ListView):
    """
    List view for legal research queries.
    """
    model = LegalResearchQuery
    template_name = 'legal_research/query_list.html'
    context_object_name = 'queries'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = LegalResearchQuery.objects.filter(
            tenant=self.request.tenant,
            created_by=self.request.user
        ).select_related('case', 'client', 'created_by')
        
        # Apply filters
        form = ResearchFilterForm(self.request.GET, request=self.request)
        if form.is_valid():
            status = form.cleaned_data.get('status')
            query_type = form.cleaned_data.get('query_type')
            case = form.cleaned_data.get('case')
            client = form.cleaned_data.get('client')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            
            if status:
                queryset = queryset.filter(status=status)
            if query_type:
                queryset = queryset.filter(query_type=query_type)
            if case:
                queryset = queryset.filter(case=case)
            if client:
                queryset = queryset.filter(client=client)
            if date_from:
                queryset = queryset.filter(created_at__gte=date_from)
            if date_to:
                queryset = queryset.filter(created_at__lte=date_to)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = ResearchFilterForm(self.request.GET, request=self.request)
        context['total_queries'] = self.get_queryset().count()
        context['completed_queries'] = self.get_queryset().filter(status='completed').count()
        context['processing_queries'] = self.get_queryset().filter(status='processing').count()
        return context


class LegalResearchQueryDetailView(LoginRequiredMixin, DetailView):
    """
    Detail view for a legal research query.
    """
    model = LegalResearchQuery
    template_name = 'legal_research/query_detail.html'
    context_object_name = 'query'
    
    def get_queryset(self):
        return LegalResearchQuery.objects.filter(
            tenant=self.request.tenant,
            created_by=self.request.user
        ).select_related('case', 'client', 'created_by').prefetch_related('sources')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['feedback_form'] = ResearchFeedbackForm(instance=self.object)
        return context


class LegalResearchQueryCreateView(LoginRequiredMixin, CreateView):
    """
    Create view for legal research queries.
    """
    model = LegalResearchQuery
    form_class = LegalResearchQueryForm
    template_name = 'legal_research/query_create.html'
    success_url = reverse_lazy('legal_research:query_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user
        
        response = super().form_valid(form)
        messages.success(self.request, 'Research query created successfully!')
        return response


class ResearchSessionListView(LoginRequiredMixin, ListView):
    """
    List view for research sessions.
    """
    model = ResearchSession
    template_name = 'legal_research/session_list.html'
    context_object_name = 'sessions'
    paginate_by = 10
    
    def get_queryset(self):
        return ResearchSession.objects.filter(
            tenant=self.request.tenant,
            created_by=self.request.user
        ).select_related('case', 'client', 'created_by').order_by('-created_at')


class ResearchSessionDetailView(LoginRequiredMixin, DetailView):
    """
    Detail view for research sessions.
    """
    model = ResearchSession
    template_name = 'legal_research/session_detail.html'
    context_object_name = 'session'
    
    def get_queryset(self):
        return ResearchSession.objects.filter(
            tenant=self.request.tenant,
            created_by=self.request.user
        ).select_related('case', 'client', 'created_by').prefetch_related('research_queries')


class ResearchSessionCreateView(LoginRequiredMixin, CreateView):
    """
    Create view for research sessions.
    """
    model = ResearchSession
    form_class = ResearchSessionForm
    template_name = 'legal_research/session_create.html'
    success_url = reverse_lazy('legal_research:session_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        form.instance.tenant = self.request.tenant
        form.instance.created_by = self.request.user
        
        response = super().form_valid(form)
        messages.success(self.request, 'Research session created successfully!')
        return response


@login_required
def quick_research(request):
    """
    Quick research view for rapid queries.
    """
    if request.method == 'POST':
        form = QuickResearchForm(request.POST)
        if form.is_valid():
            # Create research query
            query = LegalResearchQuery.objects.create(
                title=form.cleaned_data['query'][:100],
                query=form.cleaned_data['query'],
                query_type=form.cleaned_data['query_type'],
                jurisdiction=form.cleaned_data.get('jurisdiction', ''),
                tenant=request.tenant,
                created_by=request.user,
                status='pending'
            )
            
            # Process with AI
            try:
                ai_service = GeminiAIService()
                start_time = time.time()
                
                response_text, tokens_used = ai_service.research_legal_query(
                    query.query,
                    query.query_type,
                    query.jurisdiction
                )
                
                processing_time = int(time.time() - start_time)
                
                query.mark_completed(response_text, tokens_used, processing_time)
                
                messages.success(request, 'Research completed successfully!')
                return redirect('legal_research:query_detail', pk=query.pk)
                
            except Exception as e:
                query.mark_failed(str(e))
                messages.error(request, f'Research failed: {str(e)}')
                return redirect('legal_research:query_detail', pk=query.pk)
    else:
        form = QuickResearchForm()
    
    return render(request, 'legal_research/quick_research.html', {'form': form})


@login_required
def process_research_query(request, pk):
    """
    Process a research query with AI.
    """
    query = get_object_or_404(
        LegalResearchQuery,
        pk=pk,
        tenant=request.tenant,
        created_by=request.user
    )
    
    if query.status == 'processing':
        return JsonResponse({'error': 'Query is already being processed'}, status=400)
    
    if query.status == 'completed':
        return JsonResponse({'error': 'Query has already been completed'}, status=400)
    
    # Mark as processing
    query.status = 'processing'
    query.save()
    
    try:
        ai_service = GeminiAIService()
        start_time = time.time()
        
        # Prepare context
        context = {
            'case_context': query.get_case_context() if query.case else None,
            'client_context': query.get_client_context() if query.client else None,
            'documents_context': query.get_documents_context() if query.documents.exists() else None,
            'jurisdiction': query.jurisdiction,
            'practice_area': query.practice_area,
            'relevant_facts': query.relevant_facts,
            'specific_requirements': query.specific_requirements,
        }
        
        response_text, tokens_used = ai_service.research_legal_query(
            query.query,
            query.query_type,
            context
        )
        
        processing_time = int(time.time() - start_time)
        
        # Extract sources from response
        sources = ai_service.extract_sources(response_text)
        
        query.mark_completed(response_text, tokens_used, processing_time)
        
        # Create source objects
        for source_data in sources:
            ResearchSource.objects.create(
                research_query=query,
                tenant=request.tenant,
                **source_data
            )
        
        messages.success(request, 'Research completed successfully!')
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('legal_research:query_detail', kwargs={'pk': query.pk})
        })
        
    except Exception as e:
        query.mark_failed(str(e))
        return JsonResponse({'error': f'Research failed: {str(e)}'}, status=500)


@login_required
@require_POST
def submit_feedback(request, pk):
    """
    Submit feedback for a research query.
    """
    query = get_object_or_404(
        LegalResearchQuery,
        pk=pk,
        tenant=request.tenant,
        created_by=request.user
    )
    
    if query.status != 'completed':
        messages.error(request, 'Feedback can only be submitted for completed queries.')
        return redirect('legal_research:query_detail', pk=pk)
    
    form = ResearchFeedbackForm(request.POST, instance=query)
    if form.is_valid():
        form.save()
        messages.success(request, 'Thank you for your feedback!')
        return redirect('legal_research:query_detail', pk=pk)
    else:
        messages.error(request, 'Invalid feedback data.')
        return redirect('legal_research:query_detail', pk=pk)


@login_required
def document_analysis(request):
    """
    View for analyzing documents with AI.
    """
    if request.method == 'POST':
        form = DocumentAnalysisForm(request.POST, request.FILES, request=request)
        if form.is_valid():
            documents = form.cleaned_data['documents']
            analysis_type = form.cleaned_data['analysis_type']
            specific_questions = form.cleaned_data.get('specific_questions', '')
            
            try:
                analyzer = DocumentAnalyzer()
                start_time = time.time()
                
                analysis_result = analyzer.analyze_documents(
                    documents,
                    analysis_type,
                    specific_questions
                )
                
                processing_time = int(time.time() - start_time)
                
                # Create research query for the analysis
                query = LegalResearchQuery.objects.create(
                    title=f"Document Analysis: {analysis_type.replace('_', ' ').title()}",
                    query=f"Analyze {len(documents)} document(s) using {analysis_type}",
                    query_type='document_review',
                    ai_response=analysis_result,
                    ai_model_used='gemini-flash',
                    processing_time_seconds=processing_time,
                    status='completed',
                    tenant=request.tenant,
                    created_by=request.user,
                    completed_at=timezone.now()
                )
                
                # Add documents to the query
                query.documents.set(documents)
                
                messages.success(request, 'Document analysis completed successfully!')
                return redirect('legal_research:query_detail', pk=query.pk)
                
            except Exception as e:
                messages.error(request, f'Document analysis failed: {str(e)}')
    else:
        form = DocumentAnalysisForm(request=request)
    
    return render(request, 'legal_research/document_analysis.html', {'form': form})


@login_required
def research_dashboard(request):
    """
    Dashboard view for research assistant.
    """
    # Get statistics
    total_queries = LegalResearchQuery.objects.filter(
        tenant=request.tenant,
        created_by=request.user
    ).count()
    
    completed_queries = LegalResearchQuery.objects.filter(
        tenant=request.tenant,
        created_by=request.user,
        status='completed'
    ).count()
    
    processing_queries = LegalResearchQuery.objects.filter(
        tenant=request.tenant,
        created_by=request.user,
        status='processing'
    ).count()
    
    total_tokens = LegalResearchQuery.objects.filter(
        tenant=request.tenant,
        created_by=request.user,
        status='completed'
    ).aggregate(total=models.Sum('tokens_used'))['total'] or 0
    
    # Recent queries
    recent_queries = LegalResearchQuery.objects.filter(
        tenant=request.tenant,
        created_by=request.user
    ).order_by('-created_at')[:5]
    
    # Query types distribution
    query_types = LegalResearchQuery.objects.filter(
        tenant=request.tenant,
        created_by=request.user
    ).values('query_type').annotate(count=Count('id')).order_by('-count')
    
    context = {
        'total_queries': total_queries,
        'completed_queries': completed_queries,
        'processing_queries': processing_queries,
        'total_tokens': total_tokens,
        'recent_queries': recent_queries,
        'query_types': query_types,
        'success_rate': (completed_queries / total_queries * 100) if total_queries > 0 else 0,
    }
    
    return render(request, 'legal_research/dashboard.html', context)


@login_required
def export_research_results(request, pk):
    """
    Export research results to various formats.
    """
    query = get_object_or_404(
        LegalResearchQuery,
        pk=pk,
        tenant=request.tenant,
        created_by=request.user
    )
    
    if query.status != 'completed':
        messages.error(request, 'Only completed research can be exported.')
        return redirect('legal_research:query_detail', pk=pk)
    
    export_format = request.GET.get('format', 'pdf')
    
    try:
        if export_format == 'pdf':
            # Generate PDF export
            from .utils import generate_pdf_report
            pdf_content = generate_pdf_report(query)
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="research_report_{query.pk}.pdf"'
            return response
            
        elif export_format == 'docx':
            # Generate Word document export
            from .utils import generate_docx_report
            docx_content = generate_docx_report(query)
            response = HttpResponse(docx_content, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = f'attachment; filename="research_report_{query.pk}.docx"'
            return response
            
        else:
            # JSON export
            data = {
                'title': query.title,
                'query': query.query,
                'query_type': query.query_type,
                'response': query.ai_response,
                'sources': [
                    {
                        'title': source.title,
                        'citation': source.citation,
                        'summary': source.summary
                    }
                    for source in query.sources.all()
                ],
                'created_at': query.created_at.isoformat(),
                'completed_at': query.completed_at.isoformat(),
            }
            response = JsonResponse(data)
            response['Content-Disposition'] = f'attachment; filename="research_report_{query.pk}.json"'
            return response
            
    except Exception as e:
        messages.error(request, f'Export failed: {str(e)}')
        return redirect('legal_research:query_detail', pk=pk)
