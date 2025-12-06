"""
Logging utilities for multi-tenant application.

This module provides logging utilities that add tenant context to log messages
and handle tenant-specific log files.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from django.conf import settings


class TenantContextFilter(logging.Filter):
    """
    Logging filter that adds tenant context to log records.
    
    This filter adds tenant information to log records,
    making it easier to identify which tenant generated a log message.
    """
    
    def filter(self, record):
        """
        Add tenant context to the log record.
        
        Args:
            record: The log record to filter
            
        Returns:
            True to include the record in the log output
        """
        # Try to get the tenant from the current thread
        try:
            from threading import local
            _thread_local = getattr(self, '_thread_local', None)
            if _thread_local is None:
                _thread_local = local()
                self._thread_local = _thread_local
            
            # Get the tenant from the thread local storage
            tenant = getattr(_thread_local, 'tenant', None)
            
            if tenant:
                record.tenant_id = tenant.slug
                record.tenant_name = tenant.name
            else:
                record.tenant_id = 'unknown'
                record.tenant_name = 'Unknown Tenant'
        except Exception:
            # If anything goes wrong, set default values
            record.tenant_id = 'error'
            record.tenant_name = 'Error Getting Tenant'
        
        return True


class TenantFileHandler(RotatingFileHandler):
    """
    Log handler that creates tenant-specific log files.
    
    This handler creates separate log files for each tenant,
    ensuring that logs are properly isolated between tenants.
    """
    
    def __init__(self, filename=None, maxBytes=0, backupCount=0, encoding=None, delay=False):
        """
        Initialize the tenant file handler.
        
        Args:
            filename: The base filename for logs
            maxBytes: Maximum bytes before rotation
            backupCount: Number of backup files to keep
            encoding: File encoding
            delay: Whether to delay file opening
        """
        # Initialize with default values
        self.base_filename = filename or os.path.join(
            getattr(settings, 'TENANT_LOG_DIR', 'logs/tenants'),
            'tenant.log'
        )
        self.maxBytes = maxBytes or getattr(settings, 'TENANT_LOG_MAX_SIZE', 1024*1024*5)
        self.backupCount = backupCount or getattr(settings, 'TENANT_LOG_BACKUP_COUNT', 3)
        self.encoding = encoding or 'utf-8'
        
        # Initialize the base handler
        super().__init__(self.base_filename, maxBytes=self.maxBytes, 
                         backupCount=self.backupCount, encoding=self.encoding, delay=delay)
        
        # Store the current tenant
        self._tenant = None
    
    def set_tenant(self, tenant):
        """
        Set the current tenant for this handler.
        
        Args:
            tenant: The current tenant instance
        """
        self._tenant = tenant
        
        # Update the filename if we have a tenant
        if tenant:
            log_format = getattr(settings, 'TENANT_LOG_FORMAT', 'tenant_{tenant_id}.log')
            tenant_filename = log_format.format(tenant_id=tenant.slug)
            tenant_path = os.path.join(
                getattr(settings, 'TENANT_LOG_DIR', 'logs/tenants'),
                tenant_filename
            )
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(tenant_path), exist_ok=True)
            
            # Update the base filename and reconfigure the handler
            self.baseFilename = tenant_path
            self.stream = self._open()
    
    def emit(self, record):
        """
        Emit a log record to the tenant-specific file.
        
        Args:
            record: The log record to emit
        """
        # If we don't have a tenant, try to get it from the record
        if self._tenant is None and hasattr(record, 'tenant_id'):
            # Create a simple tenant object for filename generation
            class SimpleTenant:
                def __init__(self, slug):
                    self.slug = slug
            
            self.set_tenant(SimpleTenant(record.tenant_id))
        
        # If we still don't have a tenant, use a default file
        if self._tenant is None:
            # Use the base filename
            if self.baseFilename != self.base_filename:
                self.baseFilename = self.base_filename
                self.stream = self._open()
        
        # Emit the record
        super().emit(record)


def get_tenant_logger(name, tenant=None):
    """
    Get a logger configured for a specific tenant.
    
    Args:
        name: The name of the logger
        tenant: The tenant instance (optional)
        
    Returns:
        A logger instance configured for the tenant
    """
    logger = logging.getLogger(name)
    
    # If we have a tenant, add tenant-specific handlers
    if tenant:
        # Create a tenant-specific file handler
        handler = TenantFileHandler()
        handler.set_tenant(tenant)
        
        # Add the tenant context filter
        handler.addFilter(TenantContextFilter())
        
        # Add the handler to the logger
        logger.addHandler(handler)
    
    return logger


def set_current_tenant(tenant):
    """
    Set the current tenant in thread-local storage.
    
    This function should be called at the beginning of each request
    to ensure that all log messages include the tenant context.
    
    Args:
        tenant: The current tenant instance
    """
    try:
        from threading import local
        
        # Get or create the thread local storage
        if not hasattr(set_current_tenant, '_thread_local'):
            set_current_tenant._thread_local = local()
        
        # Set the tenant
        set_current_tenant._thread_local.tenant = tenant
        
        # Update all tenant file handlers
        for handler in logging.root.handlers:
            if isinstance(handler, TenantFileHandler):
                handler.set_tenant(tenant)
    except Exception:
        # If anything goes wrong, just ignore it
        pass


def get_current_tenant():
    """
    Get the current tenant from thread-local storage.
    
    Returns:
        The current tenant instance or None if not set
    """
    try:
        from threading import local
        
        # Get the thread local storage
        if hasattr(set_current_tenant, '_thread_local'):
            return getattr(set_current_tenant._thread_local, 'tenant', None)
    except Exception:
        pass
    
    return None


def clear_current_tenant():
    """
    Clear the current tenant from thread-local storage.
    
    This function should be called at the end of each request
    to clean up the tenant context.
    """
    try:
        from threading import local
        
        # Get the thread local storage
        if hasattr(set_current_tenant, '_thread_local'):
            set_current_tenant._thread_local.tenant = None
    except Exception:
        pass


class TenantLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds tenant context to log messages.
    
    This adapter automatically adds tenant information to all log messages,
    making it easier to track tenant-specific issues.
    """
    
    def process(self, msg, kwargs):
        """
        Process the log message and add tenant context.
        
        Args:
            msg: The log message
            kwargs: Additional keyword arguments
            
        Returns:
            The processed message and kwargs
        """
        # Get the current tenant
        tenant = get_current_tenant()
        
        if tenant:
            # Add tenant information to the message
            msg = f"[{tenant.slug}] {msg}"
            
            # Add tenant to the extra context if not already present
            if 'extra' not in kwargs:
                kwargs['extra'] = {}
            kwargs['extra'].update({
                'tenant_id': tenant.slug,
                'tenant_name': tenant.name,
            })
        
        return msg, kwargs