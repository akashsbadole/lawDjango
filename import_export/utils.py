import csv
import json
import io
import os
import logging
from datetime import datetime
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from .models import ImportJob, ExportJob, ImportTemplate

User = get_user_model()
logger = logging.getLogger(__name__)


class BaseImportHandler:
    """
    Base class for import handlers.
    """
    model_class = None
    field_mappings = {}
    required_fields = []
    default_values = {}
    
    def __init__(self, import_job):
        self.import_job = import_job
        self.tenant = import_job.tenant
        self.user = import_job.user
    
    def process_import(self):
        """Process the import job."""
        try:
            self.import_job.start_processing()
            
            # Read the file
            if self.import_job.file_format == 'csv':
                records = self._read_csv_file()
            elif self.import_job.file_format == 'xlsx':
                records = self._read_excel_file()
            elif self.import_job.file_format == 'json':
                records = self._read_json_file()
            else:
                raise ValueError(f"Unsupported file format: {self.import_job.file_format}")
            
            # Update total records
            self.import_job.total_records = len(records)
            self.import_job.save()
            
            # Process records
            for index, record in enumerate(records, 1):
                try:
                    self._process_record(record, index)
                    self.import_job.processed_records += 1
                    self.import_job.successful_records += 1
                except Exception as e:
                    self.import_job.add_error(
                        row_number=index,
                        error_message=str(e),
                        record_data=record
                    )
                    self.import_job.processed_records += 1
                
                # Save progress periodically
                if index % 10 == 0:
                    self.import_job.save()
            
            # Complete the import
            if self.import_job.failed_records > 0:
                error_summary = f"Import completed with {self.import_job.failed_records} errors out of {self.import_job.total_records} records."
                self.import_job.fail_processing(error_summary)
            else:
                self.import_job.complete_processing()
                
        except Exception as e:
            logger.error(f"Import failed: {str(e)}")
            self.import_job.fail_processing(str(e))
    
    def _read_csv_file(self):
        """Read CSV file and return records."""
        records = []
        with self.import_job.file.open('r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(dict(row))
        return records
    
    def _read_excel_file(self):
        """Read Excel file and return records."""
        records = []
        wb = load_workbook(filename=self.import_job.file.path)
        ws = wb.active
        
        # Get headers
        headers = []
        for cell in ws[1]:
            headers.append(cell.value)
        
        # Get data rows
        for row in ws.iter_rows(min_row=2):
            record = {}
            for i, cell in enumerate(row):
                if i < len(headers) and headers[i]:
                    record[headers[i]] = cell.value
            records.append(record)
        
        return records
    
    def _read_json_file(self):
        """Read JSON file and return records."""
        with self.import_job.file.open('r') as f:
            data = json.load(f)
            
        # Handle both single record and array of records
        if isinstance(data, list):
            return data
        else:
            return [data]
    
    def _process_record(self, record, row_number):
        """Process a single record."""
        # Map fields
        mapped_data = self._map_fields(record)
        
        # Apply default values
        mapped_data.update(self.default_values)
        
        # Add tenant and user
        mapped_data['tenant'] = self.tenant
        if self.user and hasattr(self.model_class, 'created_by'):
            mapped_data['created_by'] = self.user
        
        # Validate required fields
        self._validate_required_fields(mapped_data, row_number)
        
        # Create or update the record
        if self.import_job.update_existing:
            self._update_or_create_record(mapped_data)
        else:
            self._create_record(mapped_data)
    
    def _map_fields(self, record):
        """Map fields from the import file to model fields."""
        mapped_data = {}
        
        # Use field mappings from import job or template
        field_mappings = self.import_job.field_mappings or self.field_mappings
        
        for import_field, model_field in field_mappings.items():
            if import_field in record:
                mapped_data[model_field] = record[import_field]
        
        # Include any unmapped fields that match model fields
        for field in record:
            if field not in field_mappings and hasattr(self.model_class, field):
                mapped_data[field] = record[field]
        
        return mapped_data
    
    def _validate_required_fields(self, data, row_number):
        """Validate required fields."""
        for field in self.required_fields:
            if field not in data or not data[field]:
                raise ValueError(f"Required field '{field}' is missing or empty")
    
    def _create_record(self, data):
        """Create a new record."""
        if self.import_job.dry_run:
            return
        
        self.model_class.objects.create(**data)
    
    def _update_or_create_record(self, data):
        """Update or create a record."""
        if self.import_job.dry_run:
            return
        
        # Try to find an existing record
        lookup_field = self._get_lookup_field()
        if lookup_field and lookup_field in data:
            try:
                instance = self.model_class.objects.get(
                    tenant=self.tenant,
                    **{lookup_field: data[lookup_field]}
                )
                # Update the instance
                for field, value in data.items():
                    if hasattr(instance, field):
                        setattr(instance, field, value)
                instance.save()
            except self.model_class.DoesNotExist:
                # Create new instance
                self.model_class.objects.create(**data)
        else:
            # Create new instance
            self.model_class.objects.create(**data)
    
    def _get_lookup_field(self):
        """Get the field to use for looking up existing records."""
        # Override in subclasses
        return None


class ClientImportHandler(BaseImportHandler):
    """Import handler for Client model."""
    model_class = None  # Will be set dynamically
    field_mappings = {
        'first_name': 'first_name',
        'last_name': 'last_name',
        'email': 'email',
        'phone': 'phone',
        'address': 'address',
        'company': 'company',
        'occupation': 'occupation',
        'case_history': 'case_history',
        'notes': 'notes',
    }
    required_fields = ['first_name', 'last_name', 'email']
    default_values = {}
    
    def __init__(self, import_job):
        super().__init__(import_job)
        from clients.models import Client
        self.model_class = Client
    
    def _get_lookup_field(self):
        return 'email'


class CaseImportHandler(BaseImportHandler):
    """Import handler for Case model."""
    model_class = None  # Will be set dynamically
    field_mappings = {
        'title': 'title',
        'case_number': 'case_number',
        'description': 'description',
        'status': 'status',
        'case_type': 'case_type',
        'client_email': 'client',  # Will be converted to client ID
        'start_date': 'start_date',
        'end_date': 'end_date',
        'outcome': 'outcome',
        'notes': 'notes',
    }
    required_fields = ['title', 'case_number', 'client_email']
    default_values = {'status': 'open', 'case_type': 'civil'}
    
    def __init__(self, import_job):
        super().__init__(import_job)
        from cases.models import Case
        self.model_class = Case
    
    def _map_fields(self, record):
        """Map fields and handle client lookup."""
        mapped_data = super()._map_fields(record)
        
        # Convert client_email to client ID
        if 'client' in mapped_data and isinstance(mapped_data['client'], str):
            try:
                from clients.models import Client
                client = Client.objects.get(
                    tenant=self.tenant,
                    email=mapped_data['client']
                )
                mapped_data['client'] = client
            except Client.DoesNotExist:
                raise ValueError(f"Client with email '{mapped_data['client']}' not found")
        
        return mapped_data
    
    def _get_lookup_field(self):
        return 'case_number'


class BaseExportHandler:
    """
    Base class for export handlers.
    """
    model_class = None
    field_names = []
    related_fields = {}
    
    def __init__(self, export_job):
        self.export_job = export_job
        self.tenant = export_job.tenant
        self.user = export_job.user
    
    def process_export(self):
        """Process the export job."""
        try:
            self.export_job.start_processing()
            
            # Get the queryset
            queryset = self._get_queryset()
            
            # Update total records
            self.export_job.total_records = queryset.count()
            self.export_job.save()
            
            # Generate the file
            if self.export_job.file_format == 'csv':
                file_content = self._generate_csv(queryset)
            elif self.export_job.file_format == 'xlsx':
                file_content = self._generate_excel(queryset)
            elif self.export_job.file_format == 'json':
                file_content = self._generate_json(queryset)
            else:
                raise ValueError(f"Unsupported file format: {self.export_job.file_format}")
            
            # Save the file
            filename = self._generate_filename()
            self.export_job.file.save(filename, file_content, save=False)
            self.export_job.filename = filename
            self.export_job.processed_records = self.export_job.total_records
            self.export_job.complete_processing()
            
        except Exception as e:
            logger.error(f"Export failed: {str(e)}")
            self.export_job.fail_processing(str(e))
    
    def _get_queryset(self):
        """Get the base queryset for export."""
        queryset = self.model_class.objects.filter(tenant=self.tenant)
        
        # Apply filters
        filters = self.export_job.filters or {}
        if filters:
            queryset = queryset.filter(**filters)
        
        # Apply selected IDs
        if self.export_job.selected_ids:
            queryset = queryset.filter(id__in=self.export_job.selected_ids)
        
        # Exclude soft-deleted records if the model supports it
        if hasattr(self.model_class, 'deleted_at'):
            queryset = queryset.filter(deleted_at__isnull=True)
        
        return queryset
    
    def _generate_csv(self, queryset):
        """Generate CSV file content."""
        output = io.StringIO()
        field_names = self.export_job.field_selection or self.field_names
        
        writer = csv.DictWriter(output, fieldnames=field_names)
        writer.writeheader()
        
        for obj in queryset:
            row = self._serialize_object(obj, field_names)
            writer.writerow(row)
        
        output.seek(0)
        return io.BytesIO(output.getvalue().encode('utf-8'))
    
    def _generate_excel(self, queryset):
        """Generate Excel file content."""
        wb = Workbook()
        ws = wb.active
        ws.title = self.model_class.__name__
        
        field_names = self.export_job.field_selection or self.field_names
        
        # Write headers
        for col_num, field_name in enumerate(field_names, 1):
            ws.cell(row=1, column=col_num, value=field_name)
        
        # Write data
        for row_num, obj in enumerate(queryset, 2):
            row_data = self._serialize_object(obj, field_names)
            for col_num, field_name in enumerate(field_names, 1):
                ws.cell(row=row_num, column=col_num, value=row_data.get(field_name, ''))
        
        # Save to BytesIO
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output
    
    def _generate_json(self, queryset):
        """Generate JSON file content."""
        field_names = self.export_job.field_selection or self.field_names
        data = []
        
        for obj in queryset:
            row_data = self._serialize_object(obj, field_names)
            data.append(row_data)
        
        json_str = json.dumps(data, indent=2, default=str)
        return io.BytesIO(json_str.encode('utf-8'))
    
    def _serialize_object(self, obj, field_names):
        """Serialize an object to a dictionary."""
        data = {}
        
        for field_name in field_names:
            if '.' in field_name:
                # Handle related fields
                parts = field_name.split('.')
                value = obj
                for part in parts:
                    if hasattr(value, part):
                        value = getattr(value, part)
                    else:
                        value = ''
                        break
                data[field_name] = str(value) if value else ''
            else:
                # Handle regular fields
                if hasattr(obj, field_name):
                    value = getattr(obj, field_name)
                    if hasattr(value, '__call__'):
                        # Handle property methods
                        value = value()
                    data[field_name] = str(value) if value is not None else ''
                else:
                    data[field_name] = ''
        
        return data
    
    def _generate_filename(self):
        """Generate a filename for the export."""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        model_name = self.model_class.__name__.lower()
        return f"{model_name}_export_{timestamp}.{self.export_job.file_format}"


class ClientExportHandler(BaseExportHandler):
    """Export handler for Client model."""
    model_class = None  # Will be set dynamically
    field_names = [
        'id', 'first_name', 'last_name', 'email', 'phone', 'address',
        'company', 'occupation', 'case_history', 'notes', 'created_at'
    ]
    
    def __init__(self, export_job):
        super().__init__(export_job)
        from clients.models import Client
        self.model_class = Client


class CaseExportHandler(BaseExportHandler):
    """Export handler for Case model."""
    model_class = None  # Will be set dynamically
    field_names = [
        'id', 'title', 'case_number', 'description', 'status', 'case_type',
        'client.first_name', 'client.last_name', 'client.email',
        'start_date', 'end_date', 'outcome', 'notes', 'created_at'
    ]
    
    def __init__(self, export_job):
        super().__init__(export_job)
        from cases.models import Case
        self.model_class = Case


# Registry of import/export handlers
IMPORT_HANDLERS = {
    'clients': ClientImportHandler,
    'cases': CaseImportHandler,
}

EXPORT_HANDLERS = {
    'clients': ClientExportHandler,
    'cases': CaseExportHandler,
}


def get_import_handler(model_type, import_job):
    """Get the appropriate import handler for a model type."""
    handler_class = IMPORT_HANDLERS.get(model_type)
    if not handler_class:
        raise ValueError(f"No import handler found for model type: {model_type}")
    return handler_class(import_job)


def get_export_handler(model_type, export_job):
    """Get the appropriate export handler for a model type."""
    handler_class = EXPORT_HANDLERS.get(model_type)
    if not handler_class:
        raise ValueError(f"No export handler found for model type: {model_type}")
    return handler_class(export_job)


def process_import_job(import_job_id):
    """Process an import job (can be called from management command or Celery)."""
    try:
        import_job = ImportJob.objects.get(id=import_job_id)
        handler = get_import_handler(import_job.model_type, import_job)
        handler.process_import()
    except ImportJob.DoesNotExist:
        logger.error(f"Import job with ID {import_job_id} does not exist")
    except Exception as e:
        logger.error(f"Error processing import job {import_job_id}: {str(e)}")


def process_export_job(export_job_id):
    """Process an export job (can be called from management command or Celery)."""
    try:
        export_job = ExportJob.objects.get(id=export_job_id)
        handler = get_export_handler(export_job.model_type, export_job)
        handler.process_export()
    except ExportJob.DoesNotExist:
        logger.error(f"Export job with ID {export_job_id} does not exist")
    except Exception as e:
        logger.error(f"Error processing export job {export_job_id}: {str(e)}")