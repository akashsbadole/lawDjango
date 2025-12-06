"""
Template loaders for multi-tenant application.

This module provides template loaders that prioritize tenant-specific templates,
allowing each tenant to have their own customized templates.
"""

import os
from django.conf import settings
from django.template.loaders.filesystem import Loader as FileSystemLoader
from django.template.loaders.app_directories import Loader as AppDirectoriesLoader
from django.template.loaders.base import Loader as BaseLoader
from django.template import TemplateDoesNotExist


class TenantTemplateLoader(FileSystemLoader):
    """
    Template loader that loads tenant-specific templates.
    
    This loader checks for tenant-specific templates first,
    falling back to the default templates if not found.
    """
    
    def __init__(self, engine, dirs=None):
        """
        Initialize the tenant template loader.
        
        Args:
            engine: The template engine
            dirs: List of directories to search for templates
        """
        super().__init__(engine, dirs)
        self._tenant = None
    
    def set_tenant(self, tenant):
        """
        Set the current tenant for this loader.
        
        Args:
            tenant: The current tenant instance
        """
        self._tenant = tenant
        
        # Update the template directories if we have a tenant
        if tenant:
            # Add tenant-specific template directories
            tenant_dirs = []
            
            # Add tenant-specific directory from settings
            tenant_template_dirs = getattr(settings, 'TENANT_TEMPLATE_DIRS', [])
            for template_dir in tenant_template_dirs:
                tenant_dir = os.path.join(template_dir, tenant.slug)
                tenant_dirs.append(tenant_dir)
            
            # Add tenant-specific directory from main template dirs
            if self.dirs:
                for template_dir in self.dirs:
                    tenant_dir = os.path.join(template_dir, 'tenants', tenant.slug)
                    tenant_dirs.append(tenant_dir)
            
            # Update the template directories
            self.dirs = tenant_dirs + (self.dirs or [])
    
    def get_template_sources(self, template_name):
        """
        Get the sources for a template name.
        
        Args:
            template_name: The name of the template
            
        Yields:
            File paths to check for the template
        """
        # If we have a tenant, check tenant-specific directories first
        if self._tenant:
            # Check tenant-specific directories
            for template_dir in self.dirs:
                yield os.path.join(template_dir, template_name)
        
        # Check the default directories
        for template_dir in (self.dirs or []):
            yield os.path.join(template_dir, template_name)


class TenantAppDirectoriesLoader(AppDirectoriesLoader):
    """
    Template loader that loads tenant-specific app templates.
    
    This loader checks for tenant-specific app templates first,
    falling back to the default app templates if not found.
    """
    
    def __init__(self, engine, dirs=None):
        """
        Initialize the tenant app directories loader.
        
        Args:
            engine: The template engine
            dirs: List of directories to search for templates
        """
        super().__init__(engine, dirs)
        self._tenant = None
    
    def set_tenant(self, tenant):
        """
        Set the current tenant for this loader.
        
        Args:
            tenant: The current tenant instance
        """
        self._tenant = tenant
    
    def get_dirs(self):
        """
        Get the directories to search for templates.
        
        Returns:
            List of directories to search
        """
        dirs = super().get_dirs()
        
        # If we have a tenant, add tenant-specific directories
        if self._tenant:
            tenant_dirs = []
            
            # For each app directory, add a tenant-specific subdirectory
            for app_dir in dirs:
                tenant_dir = os.path.join(app_dir, 'tenants', self._tenant.slug)
                tenant_dirs.append(tenant_dir)
            
            # Return tenant directories first, then default directories
            return tenant_dirs + dirs
        
        return dirs


class HybridTenantLoader(BaseLoader):
    """
    Hybrid template loader that combines multiple tenant template loaders.
    
    This loader tries multiple strategies to find tenant-specific templates,
    providing maximum flexibility for template customization.
    """
    
    def __init__(self, engine, loaders=None):
        """
        Initialize the hybrid tenant loader.
        
        Args:
            engine: The template engine
            loaders: List of template loaders to use
        """
        super().__init__(engine)
        
        # Default loaders if not provided
        if loaders is None:
            loaders = [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ]
        
        # Initialize the loaders
        from django.template.engine import Engine
        from django.utils.module_loading import import_string
        
        self.loaders = []
        for loader_path in loaders:
            loader_class = import_string(loader_path)
            self.loaders.append(loader_class(engine))
        
        self._tenant = None
    
    def set_tenant(self, tenant):
        """
        Set the current tenant for all loaders.
        
        Args:
            tenant: The current tenant instance
        """
        self._tenant = tenant
        
        # Set the tenant for all loaders that support it
        for loader in self.loaders:
            if hasattr(loader, 'set_tenant'):
                loader.set_tenant(tenant)
    
    def get_template(self, template_name, skip=None):
        """
        Get a template by name.
        
        Args:
            template_name: The name of the template
            skip: List of loaders to skip
            
        Returns:
            A Template object
            
        Raises:
            TemplateDoesNotExist: If the template cannot be found
        """
        skip = skip or []
        tried = []
        
        # Try each loader in order
        for loader in self.loaders:
            if loader in skip:
                continue
            
            try:
                template = loader.get_template(template_name, skip=skip)
                return template
            except TemplateDoesNotExist as e:
                tried.extend(e.tried)
        
        # If we get here, the template was not found
        raise TemplateDoesNotExist(template_name, tried=tried)
    
    def get_contents(self, origin):
        """
        Get the contents of a template.
        
        Args:
            origin: The template origin
            
        Returns:
            The template contents
        """
        return origin.loader.get_contents(origin)