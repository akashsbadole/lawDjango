"""
Storage backends for multi-tenant application.

This module provides storage backends that organize files by tenant,
ensuring proper isolation of media files between tenants.
"""

import os
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class TenantMediaStorage(FileSystemStorage):
    """
    Storage backend that organizes media files by tenant.
    
    This storage backend automatically prefixes file paths with the tenant slug,
    ensuring that media files are properly isolated between tenants.
    """
    
    def __init__(self, location=None, base_url=None, **kwargs):
        """
        Initialize the tenant media storage.
        
        Args:
            location: The base location for storing files
            base_url: The base URL for serving files
            **kwargs: Additional keyword arguments
        """
        # Initialize with default location and base_url if not provided
        if location is None:
            location = getattr(settings, 'TENANT_MEDIA_ROOT', settings.MEDIA_ROOT)
        if base_url is None:
            base_url = getattr(settings, 'TENANT_MEDIA_URL', settings.MEDIA_URL)
            
        super().__init__(location=location, base_url=base_url, **kwargs)
        
        # Store the current tenant for use in path generation
        self._tenant = None
    
    def set_tenant(self, tenant):
        """
        Set the current tenant for this storage instance.
        
        Args:
            tenant: The current tenant instance
        """
        self._tenant = tenant
    
    def get_tenant_path(self, name):
        """
        Get the tenant-specific path for a file.
        
        Args:
            name: The original file name
            
        Returns:
            The tenant-specific file path
        """
        if self._tenant:
            # Prefix the path with the tenant slug
            return os.path.join(self._tenant.slug, name)
        return name
    
    def _save(self, name, content):
        """
        Save the file with tenant-specific path.
        
        Args:
            name: The file name
            content: The file content
            
        Returns:
            The saved file name
        """
        # Get the tenant-specific path
        tenant_name = self.get_tenant_path(name)
        
        # Ensure the tenant directory exists
        if self._tenant:
            tenant_dir = os.path.join(self.location, self._tenant.slug)
            os.makedirs(tenant_dir, exist_ok=True)
        
        # Save the file with the tenant-specific name
        return super()._save(tenant_name, content)
    
    def _open(self, name, mode='rb'):
        """
        Open the file with tenant-specific path.
        
        Args:
            name: The file name
            mode: The file mode
            
        Returns:
            The file object
        """
        # Get the tenant-specific path
        tenant_name = self.get_tenant_path(name)
        return super()._open(tenant_name, mode)
    
    def exists(self, name):
        """
        Check if a file exists with tenant-specific path.
        
        Args:
            name: The file name
            
        Returns:
            True if the file exists, False otherwise
        """
        # Get the tenant-specific path
        tenant_name = self.get_tenant_path(name)
        return super().exists(tenant_name)
    
    def delete(self, name):
        """
        Delete a file with tenant-specific path.
        
        Args:
            name: The file name
        """
        # Get the tenant-specific path
        tenant_name = self.get_tenant_path(name)
        return super().delete(tenant_name)
    
    def url(self, name):
        """
        Get the URL for a file with tenant-specific path.
        
        Args:
            name: The file name
            
        Returns:
            The URL for the file
        """
        # Get the tenant-specific path
        tenant_name = self.get_tenant_path(name)
        return super().url(tenant_name)
    
    def path(self, name):
        """
        Get the filesystem path for a file with tenant-specific path.
        
        Args:
            name: The file name
            
        Returns:
            The filesystem path for the file
        """
        # Get the tenant-specific path
        tenant_name = self.get_tenant_path(name)
        return super().path(tenant_name)
    
    def size(self, name):
        """
        Get the size of a file with tenant-specific path.
        
        Args:
            name: The file name
            
        Returns:
            The size of the file in bytes
        """
        # Get the tenant-specific path
        tenant_name = self.get_tenant_path(name)
        return super().size(tenant_name)
    
    def get_available_name(self, name, max_length=None):
        """
        Get an available filename with tenant-specific path.
        
        Args:
            name: The desired file name
            max_length: The maximum length of the filename
            
        Returns:
            An available filename
        """
        # Get the tenant-specific path
        tenant_name = self.get_tenant_path(name)
        available_name = super().get_available_name(tenant_name, max_length)
        
        # Remove the tenant prefix from the returned name
        if self._tenant and available_name.startswith(self._tenant.slug + '/'):
            return available_name[len(self._tenant.slug) + 1:]
        
        return available_name


class TenantStaticStorage(FileSystemStorage):
    """
    Storage backend for tenant-specific static files.
    
    This storage backend organizes static files by tenant,
    allowing each tenant to have their own static assets.
    """
    
    def __init__(self, location=None, base_url=None, **kwargs):
        """
        Initialize the tenant static storage.
        
        Args:
            location: The base location for storing files
            base_url: The base URL for serving files
            **kwargs: Additional keyword arguments
        """
        # Initialize with default location and base_url if not provided
        if location is None:
            location = getattr(settings, 'TENANT_STATIC_ROOT', settings.STATIC_ROOT)
        if base_url is None:
            base_url = getattr(settings, 'TENANT_STATIC_URL', settings.STATIC_URL)
            
        super().__init__(location=location, base_url=base_url, **kwargs)
        
        # Store the current tenant for use in path generation
        self._tenant = None
    
    def set_tenant(self, tenant):
        """
        Set the current tenant for this storage instance.
        
        Args:
            tenant: The current tenant instance
        """
        self._tenant = tenant
    
    def get_tenant_path(self, name):
        """
        Get the tenant-specific path for a file.
        
        Args:
            name: The original file name
            
        Returns:
            The tenant-specific file path
        """
        if self._tenant:
            # Prefix the path with the tenant slug
            return os.path.join(self._tenant.slug, name)
        return name
    
    def _save(self, name, content):
        """
        Save the file with tenant-specific path.
        
        Args:
            name: The file name
            content: The file content
            
        Returns:
            The saved file name
        """
        # Get the tenant-specific path
        tenant_name = self.get_tenant_path(name)
        
        # Ensure the tenant directory exists
        if self._tenant:
            tenant_dir = os.path.join(self.location, self._tenant.slug)
            os.makedirs(tenant_dir, exist_ok=True)
        
        # Save the file with the tenant-specific name
        return super()._save(tenant_name, content)
    
    def url(self, name):
        """
        Get the URL for a file with tenant-specific path.
        
        Args:
            name: The file name
            
        Returns:
            The URL for the file
        """
        # Get the tenant-specific path
        tenant_name = self.get_tenant_path(name)
        return super().url(tenant_name)
    
    def path(self, name):
        """
        Get the filesystem path for a file with tenant-specific path.
        
        Args:
            name: The file name
            
        Returns:
            The filesystem path for the file
        """
        # Get the tenant-specific path
        tenant_name = self.get_tenant_path(name)
        return super().path(tenant_name)