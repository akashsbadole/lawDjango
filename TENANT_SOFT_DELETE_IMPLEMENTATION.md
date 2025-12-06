# Tenant Soft Delete Implementation

This document outlines the comprehensive tenant soft delete functionality implemented for the multi-tenant law firm management system.

## Overview

The tenant soft delete functionality provides a robust system for managing tenant lifecycle, including temporary deactivation, suspension, trial expiration, and permanent deletion with data retention policies.

## Features Implemented

### 1. Enhanced Tenant Model

- **Status Field**: Added `status` field with choices: active, suspended, deleted, trial_expired
- **Status History**: Tracks all status changes with reasons and user attribution
- **Additional Fields**: `suspended_at`, `suspension_reason` for suspension tracking
- **Status Methods**: `soft_delete()`, `restore()`, `suspend()`, `unsuspend()`, `expire_trial()`
- **Validation**: `can_transition_to()` method for status transition validation
- **Display**: `get_status_display_with_icon()` for UI status display

### 2. Enhanced TenantManager

- **Query Methods**: `active()`, `suspended()`, `trial_expired()`, `deleted()`, `by_status()`, `by_plan()`
- **Action Methods**: `soft_delete()`, `restore()`, `suspend()`, `unsuspend()`, `expire_trial()`
- **Bulk Operations**: `bulk_soft_delete()`, `bulk_restore()`, `bulk_suspend()`, `bulk_unsuspend()`
- **Utility Methods**: `get_by_slug_or_404()`, `get_by_slug_any_status()`

### 3. Tenant Status History Model

- **Complete Audit Trail**: Tracks all status changes with timestamps
- **User Attribution**: Records which user performed the status change
- **Reason Tracking**: Stores the reason for each status change
- **Admin Integration**: Read-only admin interface for audit purposes

### 4. Soft Delete Views

- **Individual Actions**: Suspend, unsuspend, soft delete, restore, expire trial, permanent delete
- **Bulk Operations**: AJAX endpoint for bulk tenant operations
- **Status History**: View to display complete status change history
- **Permission Control**: Superuser-only access to sensitive operations

### 5. Enhanced Middleware

- **Status Handling**: Proper response based on tenant status
- **Error Pages**: Custom pages for suspended, trial expired, and inactive tenants
- **API Support**: JSON responses for API requests
- **Graceful Degradation**: Maintains user experience during tenant issues

### 6. Management Commands

- **cleanup_deleted_tenants**: Permanently removes tenants after retention period
- **restore_suspended_tenants**: Bulk restores suspended tenants
- **check_tenant_status**: Reports tenant status statistics and recent changes
- **bulk_status_update**: Bulk updates tenant status with validation

### 7. Email Notifications

- **Status Change Notifications**: Emails for all status transitions
- **Warning System**: Advance warnings for deletion, suspension, and trial expiration
- **Template Support**: HTML email templates with context
- **Admin Notification**: Copies to tenant administrators

### 8. Admin Interface

- **Status Display**: Visual status indicators with icons
- **Bulk Actions**: Admin actions for multiple tenant operations
- **Filtering**: Filter by status, plan, and deleted state
- **Audit Trail**: Integrated status history viewing

### 9. Templates

- **Status Pages**: Dedicated pages for suspended, trial expired, inactive tenants
- **Confirmation Dialogs**: Proper confirmation flows for destructive actions
- **User Feedback**: Clear messaging about tenant status and next steps

## Usage Examples

### Soft Deleting a Tenant

```python
# Via model method
tenant.soft_delete(reason="Violation of terms", changed_by=request.user)

# Via manager
Tenant.objects.soft_delete(tenant.id, reason="Violation of terms", changed_by=request.user)

# Via view
POST /tenants/123/soft-delete/
```

### Bulk Operations

```python
# Via command
python manage.py bulk_status_update --status=suspended --tenant-ids="1,2,3" --reason="Non-payment"

# Via admin
Select tenants → Action → Soft delete selected
```

### Status History

```python
# View history
GET /tenants/123/status-history/

# Query history
history = tenant.status_history.all()
```

## Configuration

Add these settings to your Django settings:

```python
# Email settings
DEFAULT_FROM_EMAIL = 'noreply@lawfirm.com'
SITE_NAME = 'Law Firm Management'

# Retention policies
TENANT_DELETION_WARNING_DAYS = 7
TRIAL_EXPIRATION_WARNING_DAYS = 7
DELETED_TENANT_RETENTION_DAYS = 90
STATUS_HISTORY_RETENTION_DAYS = 365
```

## Migration

Run the migration to apply database changes:

```bash
python manage.py migrate
```

## Security Considerations

1. **Permission Control**: All sensitive operations require superuser status
2. **Audit Trail**: All status changes are logged with user attribution
3. **Data Retention**: Configurable retention policies before permanent deletion
4. **Validation**: Status transitions are validated before execution
5. **Confirmation**: Destructive actions require explicit confirmation

## Best Practices

1. **Always use soft delete** instead of permanent deletion when possible
2. **Provide clear reasons** for all status changes
3. **Set appropriate retention periods** based on business requirements
4. **Monitor status history** for auditing and troubleshooting
5. **Test status transitions** in development environment