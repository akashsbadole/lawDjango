import json
import csv
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from .models import ImportJob, ExportJob, ImportTemplate
from .forms import (
    ImportJobForm, ImportJobUpdateForm, ExportJobForm, 
    ImportTemplateForm, FieldMappingForm, ExportFilterForm
)
from .utils import process_import_job, process_export_job, get_import_handler


class ImportJobListView(LoginRequiredMixin, ListView):
    """List all import jobs for the current tenant."""
    model = ImportJob
    template_name = 'import_export/import_job_list.html'
    context_object_name = 'import_jobs'
    paginate_by = 20
    
    def get_queryset(self):
        """Filter import jobs by tenant."""
        return ImportJob.objects.filter(tenant=self.request.tenant).select_related('user')
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Import Jobs'
        return context


class ImportJobDetailView(LoginRequiredMixin, DetailView):
    """Display details of an import job."""
    model = ImportJob
    template_name = 'import_export/import_job_detail.html'
    context_object_name = 'import_job'
    
    def get_queryset(self):
        """Filter import jobs by tenant."""
        return ImportJob.objects.filter(tenant=self.request.tenant).select_related('user')
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = f'Import Job: {self.object.id}'
        return context


class ImportJobCreateView(LoginRequiredMixin, CreateView):
    """Create a new import job."""
    model = ImportJob
    form_class = ImportJobForm
    template_name = 'import_export/import_job_form.html'
    success_url = reverse_lazy('import_export:import_job_list')
    
    def get_form_kwargs(self):
        """Pass tenant and user to form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Import Job'
        context['templates'] = ImportTemplate.objects.filter(
            tenant=self.request.tenant
        ).filter(model_type=self.request.POST.get('model_type', 'clients'))
        return context
    
    def form_valid(self, form):
        """Process the form and start the import job."""
        response = super().form_valid(form)
        messages.success(self.request, 'Import job created successfully. Processing will begin shortly.')
        
        # Process the import job
        try:
            process_import_job(self.object.id)
        except Exception as e:
            messages.error(self.request, f'Error starting import job: {str(e)}')
        
        return response


class ImportJobUpdateView(LoginRequiredMixin, UpdateView):
    """Update an import job."""
    model = ImportJob
    form_class = ImportJobUpdateForm
    template_name = 'import_export/import_job_update.html'
    success_url = reverse_lazy('import_export:import_job_list')
    
    def get_queryset(self):
        """Filter import jobs by tenant."""
        return ImportJob.objects.filter(tenant=self.request.tenant)
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = f'Update Import Job: {self.object.id}'
        return context
    
    def form_valid(self, form):
        """Process the form and restart the import job if needed."""
        response = super().form_valid(form)
        messages.success(self.request, 'Import job updated successfully.')
        
        # Restart the import job if it was pending or failed
        if self.object.status in ['pending', 'failed']:
            try:
                process_import_job(self.object.id)
            except Exception as e:
                messages.error(self.request, f'Error restarting import job: {str(e)}')
        
        return response


class ImportJobDeleteView(LoginRequiredMixin, DeleteView):
    """Delete an import job."""
    model = ImportJob
    template_name = 'import_export/import_job_confirm_delete.html'
    success_url = reverse_lazy('import_export:import_job_list')
    
    def get_queryset(self):
        """Filter import jobs by tenant."""
        return ImportJob.objects.filter(tenant=self.request.tenant)
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = f'Delete Import Job: {self.object.id}'
        return context
    
    def delete(self, request, *args, **kwargs):
        """Delete the import job and its file."""
        obj = self.get_object()
        
        # Delete the file if it exists
        if obj.file:
            obj.file.delete()
        
        messages.success(request, 'Import job deleted successfully.')
        return super().delete(request, *args, **kwargs)


class ExportJobListView(LoginRequiredMixin, ListView):
    """List all export jobs for the current tenant."""
    model = ExportJob
    template_name = 'import_export/export_job_list.html'
    context_object_name = 'export_jobs'
    paginate_by = 20
    
    def get_queryset(self):
        """Filter export jobs by tenant."""
        return ExportJob.objects.filter(tenant=self.request.tenant).select_related('user')
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Export Jobs'
        return context


class ExportJobDetailView(LoginRequiredMixin, DetailView):
    """Display details of an export job."""
    model = ExportJob
    template_name = 'import_export/export_job_detail.html'
    context_object_name = 'export_job'
    
    def get_queryset(self):
        """Filter export jobs by tenant."""
        return ExportJob.objects.filter(tenant=self.request.tenant).select_related('user')
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = f'Export Job: {self.object.id}'
        return context


class ExportJobCreateView(LoginRequiredMixin, CreateView):
    """Create a new export job."""
    model = ExportJob
    form_class = ExportJobForm
    template_name = 'import_export/export_job_form.html'
    success_url = reverse_lazy('import_export:export_job_list')
    
    def get_form_kwargs(self):
        """Pass tenant and user to form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Export Job'
        return context
    
    def form_valid(self, form):
        """Process the form and start the export job."""
        response = super().form_valid(form)
        messages.success(self.request, 'Export job created successfully. Processing will begin shortly.')
        
        # Process the export job
        try:
            process_export_job(self.object.id)
        except Exception as e:
            messages.error(self.request, f'Error starting export job: {str(e)}')
        
        return response


class ExportJobDeleteView(LoginRequiredMixin, DeleteView):
    """Delete an export job."""
    model = ExportJob
    template_name = 'import_export/export_job_confirm_delete.html'
    success_url = reverse_lazy('import_export:export_job_list')
    
    def get_queryset(self):
        """Filter export jobs by tenant."""
        return ExportJob.objects.filter(tenant=self.request.tenant)
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = f'Delete Export Job: {self.object.id}'
        return context
    
    def delete(self, request, *args, **kwargs):
        """Delete the export job and its file."""
        obj = self.get_object()
        
        # Delete the file if it exists
        if obj.file:
            obj.file.delete()
        
        messages.success(request, 'Export job deleted successfully.')
        return super().delete(request, *args, **kwargs)


class ImportTemplateListView(LoginRequiredMixin, ListView):
    """List all import templates for the current tenant."""
    model = ImportTemplate
    template_name = 'import_export/import_template_list.html'
    context_object_name = 'templates'
    paginate_by = 20
    
    def get_queryset(self):
        """Filter templates by tenant and include public templates."""
        return ImportTemplate.objects.filter(
            Q(tenant=self.request.tenant) | Q(is_public=True)
        ).select_related('created_by')
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Import Templates'
        return context


class ImportTemplateDetailView(LoginRequiredMixin, DetailView):
    """Display details of an import template."""
    model = ImportTemplate
    template_name = 'import_export/import_template_detail.html'
    context_object_name = 'template'
    
    def get_queryset(self):
        """Filter templates by tenant and include public templates."""
        return ImportTemplate.objects.filter(
            Q(tenant=self.request.tenant) | Q(is_public=True)
        ).select_related('created_by')
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = f'Import Template: {self.object.name}'
        return context


class ImportTemplateCreateView(LoginRequiredMixin, CreateView):
    """Create a new import template."""
    model = ImportTemplate
    form_class = ImportTemplateForm
    template_name = 'import_export/import_template_form.html'
    success_url = reverse_lazy('import_export:import_template_list')
    
    def get_form_kwargs(self):
        """Pass tenant and user to form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Import Template'
        return context
    
    def form_valid(self, form):
        """Process the form."""
        response = super().form_valid(form)
        messages.success(self.request, 'Import template created successfully.')
        return response


class ImportTemplateUpdateView(LoginRequiredMixin, UpdateView):
    """Update an import template."""
    model = ImportTemplate
    form_class = ImportTemplateForm
    template_name = 'import_export/import_template_form.html'
    success_url = reverse_lazy('import_export:import_template_list')
    
    def get_queryset(self):
        """Filter templates by tenant."""
        return ImportTemplate.objects.filter(tenant=self.request.tenant)
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = f'Update Import Template: {self.object.name}'
        return context
    
    def form_valid(self, form):
        """Process the form."""
        response = super().form_valid(form)
        messages.success(self.request, 'Import template updated successfully.')
        return response


class ImportTemplateDeleteView(LoginRequiredMixin, DeleteView):
    """Delete an import template."""
    model = ImportTemplate
    template_name = 'import_export/import_template_confirm_delete.html'
    success_url = reverse_lazy('import_export:import_template_list')
    
    def get_queryset(self):
        """Filter templates by tenant."""
        return ImportTemplate.objects.filter(tenant=self.request.tenant)
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        context['title'] = f'Delete Import Template: {self.object.name}'
        return context
    
    def delete(self, request, *args, **kwargs):
        """Delete the import template and its sample file."""
        obj = self.get_object()
        
        # Delete the sample file if it exists
        if obj.sample_file:
            obj.sample_file.delete()
        
        messages.success(request, 'Import template deleted successfully.')
        return super().delete(request, *args, **kwargs)


@login_required
def preview_import_file(request):
    """Preview an import file and extract headers."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        file = request.FILES.get('file')
        file_format = request.POST.get('file_format', 'csv')
        skip_header = request.POST.get('skip_header', 'true').lower() == 'true'
        
        if not file:
            return JsonResponse({'error': 'No file provided'}, status=400)
        
        # Extract headers based on file format
        if file_format == 'csv':
            headers = _extract_csv_headers(file, skip_header)
        elif file_format == 'xlsx':
            headers = _extract_excel_headers(file, skip_header)
        else:
            return JsonResponse({'error': f'Unsupported file format: {file_format}'}, status=400)
        
        # Get model fields based on model type
        model_type = request.POST.get('model_type', 'clients')
        model_fields = _get_model_fields(model_type)
        
        return JsonResponse({
            'headers': headers,
            'model_fields': model_fields
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def _extract_csv_headers(file, skip_header=True):
    """Extract headers from a CSV file."""
    headers = []
    content = file.read().decode('utf-8')
    file.seek(0)  # Reset file pointer
    
    reader = csv.reader(io.StringIO(content))
    for i, row in enumerate(reader):
        if i == 0 and skip_header:
            headers = row
            break
        elif not skip_header:
            # Use the first row as headers if not skipping
            headers = [f'Column {j+1}' for j in range(len(row))]
            break
    
    return headers


def _extract_excel_headers(file, skip_header=True):
    """Extract headers from an Excel file."""
    headers = []
    
    # Save the uploaded file temporarily
    temp_path = f'/tmp/{file.name}'
    with open(temp_path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)
    
    try:
        # Simple Excel header extraction without openpyxl dependency
        # This is a simplified version that just uses column letters
        if not skip_header:
            headers = [f'Column {chr(65+i)}' for i in range(26)]  # A-Z columns
        else:
            # If skipping header, we can't easily extract headers without additional libraries
            # For now, return empty headers
            headers = []
    finally:
        # Clean up the temporary file
        import os
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    return headers


def _get_model_fields(model_type):
    """Get field names for a model type."""
    if model_type == 'clients':
        return [
            'first_name', 'last_name', 'email', 'phone', 'address',
            'company', 'occupation', 'case_history', 'notes'
        ]
    elif model_type == 'cases':
        return [
            'title', 'case_number', 'description', 'status', 'case_type',
            'client', 'start_date', 'end_date', 'outcome', 'notes'
        ]
    else:
        return []


@login_required
def download_export_file(request, pk):
    """Download an export file."""
    export_job = get_object_or_404(
        ExportJob.objects.filter(tenant=request.tenant),
        pk=pk
    )
    
    if not export_job.file or export_job.status != 'completed':
        raise Http404("Export file not available")
    
    # Serve the file
    response = HttpResponse(export_job.file.read(), content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{export_job.filename}"'
    return response


@login_required
def get_export_filters(request):
    """Get filter form for a model type."""
    model_type = request.GET.get('model_type', 'clients')
    
    if model_type == 'clients':
        form = ExportFilterForm(model_type='clients')
    elif model_type == 'cases':
        form = ExportFilterForm(model_type='cases')
    else:
        form = ExportFilterForm()
    
    template_name = 'import_export/partials/export_filters.html'
    return render(request, template_name, {'form': form})


@login_required
def get_model_fields(request):
    """Get field names for a model type."""
    model_type = request.GET.get('model_type', 'clients')
    fields = _get_model_fields(model_type)
    
    return JsonResponse({'fields': fields})


@login_required
@require_POST
def cancel_import_job(request, pk):
    """Cancel an import job."""
    import_job = get_object_or_404(
        ImportJob.objects.filter(tenant=request.tenant),
        pk=pk
    )
    
    if import_job.status in ['pending', 'processing']:
        import_job.cancel_processing()
        messages.success(request, 'Import job cancelled successfully.')
    else:
        messages.error(request, 'Cannot cancel a completed import job.')
    
    return redirect('import_export:import_job_detail', pk=pk)


@login_required
@require_POST
def cancel_export_job(request, pk):
    """Cancel an export job."""
    export_job = get_object_or_404(
        ExportJob.objects.filter(tenant=request.tenant),
        pk=pk
    )
    
    if export_job.status in ['pending', 'processing']:
        export_job.cancel_processing()
        messages.success(request, 'Export job cancelled successfully.')
    else:
        messages.error(request, 'Cannot cancel a completed export job.')
    
    return redirect('import_export:export_job_detail', pk=pk)


@login_required
def import_job_status(request, pk):
    """Get the status of an import job as JSON."""
    import_job = get_object_or_404(
        ImportJob.objects.filter(tenant=request.tenant),
        pk=pk
    )
    
    data = {
        'status': import_job.status,
        'progress_percentage': import_job.progress_percentage,
        'total_records': import_job.total_records,
        'processed_records': import_job.processed_records,
        'successful_records': import_job.successful_records,
        'failed_records': import_job.failed_records,
        'errors': import_job.errors,
        'error_summary': import_job.error_summary,
    }
    
    return JsonResponse(data)


@login_required
def export_job_status(request, pk):
    """Get the status of an export job as JSON."""
    export_job = get_object_or_404(
        ExportJob.objects.filter(tenant=request.tenant),
        pk=pk
    )
    
    data = {
        'status': export_job.status,
        'progress_percentage': export_job.progress_percentage,
        'total_records': export_job.total_records,
        'processed_records': export_job.processed_records,
        'download_url': export_job.download_url,
        'errors': export_job.errors,
        'error_summary': export_job.error_summary,
    }
    
    return JsonResponse(data)