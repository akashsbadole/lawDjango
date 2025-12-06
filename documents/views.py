import os
import mimetypes
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views.generic.edit import FormMixin
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse, Http404, JsonResponse
from django.core.exceptions import PermissionDenied
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
from django.contrib.auth import get_user_model

from tenants.models import Tenant
from .models import Document
from .forms import DocumentForm, DocumentUpdateForm, DocumentVersionForm, DocumentSearchForm
from permissions.utils import TenantPermissionRequiredMixin
from audit.utils import log_activity

User = get_user_model()


class TenantRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user belongs to a tenant.
    """
    def test_func(self):
        return self.request.user.is_authenticated and hasattr(self.request.user, 'tenant')
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('account_login')
        return redirect('home')


class DocumentListView(TenantPermissionRequiredMixin, ListView, FormMixin):
    """
    List view for documents with search and filtering capabilities.
    """
    model = Document
    template_name = 'documents/document_list.html'
    context_object_name = 'documents'
    paginate_by = 20
    form_class = DocumentSearchForm
    permission_required = 'documents.view_document'
    
    def get_queryset(self):
        """
        Filter documents by tenant and search criteria.
        """
        tenant = self.request.user.tenant
        queryset = Document.objects.accessible_by(self.request.user, tenant)
        
        # Get search form data
        form = self.get_form()
        if form.is_valid():
            cleaned_data = form.cleaned_data
            
            # Apply filters
            if cleaned_data.get('query'):
                queryset = queryset.search(cleaned_data['query'], tenant)
            
            if cleaned_data.get('category'):
                queryset = queryset.filter(category=cleaned_data['category'])
            
            if cleaned_data.get('access_level'):
                queryset = queryset.filter(access_level=cleaned_data['access_level'])
            
            if cleaned_data.get('file_type'):
                queryset = queryset.filter(file_type=cleaned_data['file_type'])
            
            if cleaned_data.get('case'):
                queryset = queryset.filter(case=cleaned_data['case'])
            
            if cleaned_data.get('client'):
                queryset = queryset.filter(client=cleaned_data['client'])
            
            if cleaned_data.get('tags'):
                queryset = queryset.with_tags(cleaned_data['tags'], tenant)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        """
        Add additional context to the template.
        """
        context = super().get_context_data(**kwargs)
        context['search_form'] = self.get_form()
        context['total_documents'] = self.get_queryset().count()
        context['storage_used'] = Document.objects.get_storage_usage(self.request.user.tenant)
        context['storage_limit'] = self.request.user.tenant.max_storage_mb * 1024 * 1024
        context['storage_percentage'] = (context['storage_used'] / context['storage_limit']) * 100
        return context
    
    def get_form_kwargs(self):
        """
        Pass tenant to the form.
        """
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.user.tenant
        return kwargs


class DocumentDetailView(TenantPermissionRequiredMixin, DetailView):
    """
    Detail view for a single document.
    """
    model = Document
    template_name = 'documents/document_detail.html'
    context_object_name = 'document'
    permission_required = 'documents.view_document'
    
    def get_object(self, queryset=None):
        """
        Get the document object and check permissions.
        """
        obj = super().get_object(queryset)
        if not obj.can_be_accessed_by(self.request.user):
            raise PermissionDenied("You don't have permission to access this document.")
        return obj
    
    def get_context_data(self, **kwargs):
        """
        Add additional context to the template.
        """
        context = super().get_context_data(**kwargs)
        document = self.get_object()
        
        # Get document versions
        context['versions'] = Document.objects.filter(
            parent_document=document.parent_document or document
        ).order_by('-version')
        
        # Get related documents (same case or client)
        related_docs = Document.objects.filter(
            tenant=self.request.user.tenant
        ).exclude(pk=document.pk)
        
        if document.case:
            related_docs = related_docs.filter(case=document.case)
        elif document.client:
            related_docs = related_docs.filter(client=document.client)
        
        context['related_documents'] = related_docs[:5]
        
        return context


class DocumentCreateView(TenantPermissionRequiredMixin, CreateView):
    """
    Create view for uploading new documents.
    """
    model = Document
    form_class = DocumentForm
    template_name = 'documents/document_form.html'
    success_url = reverse_lazy('documents:list')
    permission_required = 'documents.add_document'
    
    def get_form_kwargs(self):
        """
        Pass user and tenant to the form.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['tenant'] = self.request.user.tenant
        return kwargs
    
    def form_valid(self, form):
        """
        Handle successful form submission.
        """
        document = form.save()
        
        # Log activity
        log_activity(
            tenant=self.request.tenant,
            user=self.request.user,
            activity_type='DOCUMENT_UPLOADED',
            description=f'Uploaded new document: {document.title}',
            related_object=document,
            metadata={
                'file_name': document.file_name,
                'file_size': document.file_size,
                'file_type': document.file_type,
                'category': document.category,
            }
        )
        
        messages.success(
            self.request,
            f'Document "{document.title}" has been uploaded successfully.'
        )
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        """
        Add additional context to the template.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = 'Upload New Document'
        context['action'] = 'Upload'
        return context


class DocumentUpdateView(TenantPermissionRequiredMixin, UpdateView):
    """
    Update view for editing document details.
    """
    model = Document
    form_class = DocumentUpdateForm
    template_name = 'documents/document_form.html'
    success_url = reverse_lazy('documents:list')
    permission_required = 'documents.change_document'
    
    def get_object(self, queryset=None):
        """
        Get the document object and check permissions.
        """
        obj = super().get_object(queryset)
        if not obj.can_be_accessed_by(self.request.user):
            raise PermissionDenied("You don't have permission to edit this document.")
        return obj
    
    def get_form_kwargs(self):
        """
        Pass user and tenant to the form.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['tenant'] = self.request.user.tenant
        return kwargs
    
    def form_valid(self, form):
        """
        Handle successful form submission.
        """
        # Get old values for audit
        old_values = {
            'title': self.object.title,
            'description': self.object.description,
            'category': self.object.category,
            'access_level': self.object.access_level,
        }
        
        document = form.save()
        
        # Log activity with changes
        log_activity(
            tenant=self.request.tenant,
            user=self.request.user,
            activity_type='DOCUMENT_UPDATED',
            description=f'Updated document: {document.title}',
            related_object=document,
            metadata={
                'old_values': old_values,
                'new_values': {
                    'title': document.title,
                    'description': document.description,
                    'category': document.category,
                    'access_level': document.access_level,
                }
            }
        )
        
        messages.success(
            self.request,
            f'Document "{document.title}" has been updated successfully.'
        )
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        """
        Add additional context to the template.
        """
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Document'
        context['action'] = 'Update'
        return context


class DocumentDeleteView(TenantPermissionRequiredMixin, DeleteView):
    """
    Delete view for documents (soft delete).
    """
    model = Document
    template_name = 'documents/document_confirm_delete.html'
    success_url = reverse_lazy('documents:list')
    permission_required = 'documents.delete_document'
    
    def get_object(self, queryset=None):
        """
        Get the document object and check permissions.
        """
        obj = super().get_object(queryset)
        if not obj.can_be_accessed_by(self.request.user):
            raise PermissionDenied("You don't have permission to delete this document.")
        return obj
    
    def delete(self, request, *args, **kwargs):
        """
        Perform soft delete on the document.
        """
        obj = self.get_object()
        obj.soft_delete()
        messages.success(
            request,
            f'Document "{obj.title}" has been deleted successfully.'
        )
        return redirect(self.get_success_url())


@login_required
def document_download(request, pk):
    """
    View to download a document file with permission checking.
    """
    document = get_object_or_404(Document, pk=pk)
    
    # Check if user has permission to access this document
    if not document.can_be_accessed_by(request.user):
        raise PermissionDenied("You don't have permission to download this document.")
    
    # Check if file exists
    if not document.file or not os.path.exists(document.file.path):
        raise Http404("File not found.")
    
    # Get file content type
    content_type, _ = mimetypes.guess_type(document.file.name)
    if content_type is None:
        content_type = 'application/octet-stream'
    
    # Serve the file
    response = HttpResponse(document.file.read(), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{document.file_name}"'
    response['Content-Length'] = document.file_size
    
    return response


class DocumentVersionCreateView(TenantPermissionRequiredMixin, CreateView):
    """
    Create view for uploading a new version of an existing document.
    """
    model = Document
    form_class = DocumentVersionForm
    template_name = 'documents/document_version_form.html'
    permission_required = 'documents.change_document'  # Using change as it's modifying document
    
    def dispatch(self, request, *args, **kwargs):
        """
        Get the parent document and check permissions.
        """
        self.parent_document = get_object_or_404(Document, pk=kwargs['pk'])
        if not self.parent_document.can_be_accessed_by(request.user):
            raise PermissionDenied("You don't have permission to add versions to this document.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """
        Pass tenant and parent document to the form.
        """
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.user.tenant
        kwargs['parent_document'] = self.parent_document
        return kwargs
    
    def form_valid(self, form):
        """
        Create new version of the document.
        """
        new_version = self.parent_document.create_new_version(
            form.cleaned_data['file'],
            user=self.request.user
        )
        messages.success(
            self.request,
            f'New version {new_version.version} of "{new_version.title}" has been uploaded successfully.'
        )
        return redirect('documents:detail', pk=new_version.pk)
    
    def get_context_data(self, **kwargs):
        """
        Add additional context to the template.
        """
        context = super().get_context_data(**kwargs)
        context['parent_document'] = self.parent_document
        context['title'] = f'Upload New Version - {self.parent_document.title}'
        return context


@method_decorator(require_POST, name='dispatch')
@login_required
def document_toggle_star(request, pk):
    """
    Toggle star status for a document (AJAX endpoint).
    """
    document = get_object_or_404(Document, pk=pk)
    
    if not document.can_be_accessed_by(request.user):
        raise PermissionDenied("You don't have permission to access this document.")
    
    # This would require adding a starred_by ManyToMany field to the Document model
    # For now, we'll return a simple response
    is_starred = False  # Placeholder logic
    
    return JsonResponse({
        'success': True,
        'is_starred': is_starred,
        'message': 'Document starred successfully.' if is_starred else 'Document unstarred successfully.'
    })


@login_required
def document_stats(request):
    """
    Get document statistics for the current tenant (AJAX endpoint).
    """
    if not hasattr(request.user, 'tenant'):
        return JsonResponse({'error': 'No tenant found'}, status=400)
    
    tenant = request.user.tenant
    stats = {
        'total_documents': Document.objects.for_tenant(tenant).count(),
        'total_size': Document.objects.get_storage_usage(tenant),
        'by_category': list(
            Document.objects.for_tenant(tenant).values('category')
            .annotate(count=Count('id'))
            .order_by('-count')
        ),
        'by_type': list(
            Document.objects.for_tenant(tenant).values('file_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        ),
        'recent_uploads': Document.objects.for_tenant(tenant).order_by('-created_at')[:5].count(),
    }
    
    return JsonResponse(stats)
