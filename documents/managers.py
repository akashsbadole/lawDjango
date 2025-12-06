from django.db import models
from django.utils import timezone


class DocumentManager(models.Manager):
    """
    Manager for the Document model with tenant filtering and soft delete functionality.
    """
    
    def get_queryset(self):
        """
        Override the default queryset to exclude soft-deleted documents.
        """
        return super().get_queryset().filter(deleted_at__isnull=True)
    
    def all_with_deleted(self):
        """
        Return all documents including soft-deleted ones.
        """
        return super().get_queryset()
    
    def deleted(self):
        """
        Return only soft-deleted documents.
        """
        return super().get_queryset().filter(deleted_at__isnull=False)
    
    def for_tenant(self, tenant):
        """
        Filter documents by tenant.
        """
        return self.filter(tenant=tenant)
    
    def active_for_tenant(self, tenant):
        """
        Return active (non-deleted) documents for a specific tenant.
        """
        return self.filter(tenant=tenant, deleted_at__isnull=True)
    
    def by_category(self, category, tenant=None):
        """
        Filter documents by category, optionally by tenant.
        """
        queryset = self.filter(category=category)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def by_access_level(self, access_level, tenant=None):
        """
        Filter documents by access level, optionally by tenant.
        """
        queryset = self.filter(access_level=access_level)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def by_case(self, case, tenant=None):
        """
        Filter documents by case, optionally by tenant.
        """
        queryset = self.filter(case=case)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def by_client(self, client, tenant=None):
        """
        Filter documents by client, optionally by tenant.
        """
        queryset = self.filter(client=client)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def uploaded_by(self, user, tenant=None):
        """
        Filter documents uploaded by a specific user, optionally by tenant.
        """
        queryset = self.filter(uploaded_by=user)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def latest_versions(self, tenant=None):
        """
        Return only the latest versions of documents.
        """
        queryset = self.filter(is_latest_version=True)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def by_file_type(self, file_type, tenant=None):
        """
        Filter documents by file type, optionally by tenant.
        """
        queryset = self.filter(file_type=file_type)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def with_tags(self, tags, tenant=None):
        """
        Filter documents that contain any of the specified tags.
        Tags should be a list or comma-separated string.
        """
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(',')]
        
        queryset = self.all()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        
        # Build Q objects for each tag
        from django.db.models import Q
        q_objects = Q()
        for tag in tags:
            q_objects |= Q(tags__icontains=tag)
        
        return queryset.filter(q_objects).distinct()
    
    def search(self, query, tenant=None):
        """
        Search documents by title, description, filename, or tags.
        """
        queryset = self.all()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        
        if query:
            queryset = queryset.filter(
                models.Q(title__icontains=query) |
                models.Q(description__icontains=query) |
                models.Q(file_name__icontains=query) |
                models.Q(tags__icontains=query) |
                models.Q(case__title__icontains=query) |
                models.Q(case__case_number__icontains=query) |
                models.Q(client__first_name__icontains=query) |
                models.Q(client__last_name__icontains=query) |
                models.Q(client__email__icontains=query)
            )
        
        return queryset
    
    def accessible_by(self, user, tenant=None):
        """
        Return documents that can be accessed by the given user.
        """
        queryset = self.all()
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        
        # If user is not authenticated, return empty queryset
        if not user.is_authenticated:
            return queryset.none()
        
        # Superusers can access all documents
        if user.is_superuser:
            return queryset
        
        # Filter by user's tenant
        queryset = queryset.filter(tenant=user.tenant)
        
        # Users can always access their own uploaded documents
        user_docs = queryset.filter(uploaded_by=user)
        
        # Check access levels based on user role
        if user.role == 'admin':
            # Admins can access all documents in their tenant
            return queryset
        elif user.role == 'lawyer':
            # Lawyers can access public, internal, and confidential documents
            # and restricted documents for their assigned cases
            accessible_docs = queryset.filter(
                models.Q(access_level__in=['public', 'internal', 'confidential']) |
                models.Q(access_level='restricted', case__assigned_lawyers=user)
            )
            return (user_docs | accessible_docs).distinct()
        else:
            # Other roles can only access public and internal documents
            accessible_docs = queryset.filter(access_level__in=['public', 'internal'])
            return (user_docs | accessible_docs).distinct()
    
    def create_document(self, tenant, user, file_obj, **kwargs):
        """
        Create a new document with tenant and user information.
        """
        return self.create(
            tenant=tenant,
            uploaded_by=user,
            file=file_obj,
            **kwargs
        )
    
    def soft_delete(self, document_id):
        """
        Soft delete a document by setting the deleted_at timestamp.
        """
        document = self.get(pk=document_id)
        document.deleted_at = timezone.now()
        document.save()
        return document
    
    def get_storage_usage(self, tenant):
        """
        Calculate total storage usage for a tenant in bytes.
        """
        return self.filter(tenant=tenant).aggregate(
            total_size=models.Sum('file_size')
        )['total_size'] or 0
    
    def get_storage_usage_by_type(self, tenant):
        """
        Calculate storage usage by file type for a tenant.
        """
        return self.filter(tenant=tenant).values('file_type').annotate(
            total_size=models.Sum('file_size'),
            count=models.Count('id')
        ).order_by('-total_size')
    
    def get_recent_documents(self, tenant=None, days=30):
        """
        Return documents created within the specified number of days.
        """
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        queryset = self.filter(created_at__gte=cutoff_date)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def get_large_documents(self, tenant=None, size_mb=10):
        """
        Return documents larger than the specified size in MB.
        """
        size_bytes = size_mb * 1024 * 1024
        queryset = self.filter(file_size__gt=size_bytes)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset