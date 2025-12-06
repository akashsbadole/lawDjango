# ERR_TOO_MANY_REDIRECTS Fix Documentation

This document outlines the comprehensive fix implemented for the ERR_TOO_MANY_REDIRECTS issue that was occurring during login in the multi-tenant lawyer management system.

## Problem Summary

Users were experiencing infinite redirect loops when attempting to log in to the system. The issue was particularly affecting:
- Lawyers trying to access their dashboard
- Admin users attempting to reach tenant-specific pages
- Users without proper tenant assignments

## Root Causes Identified

1. **Missing Tenant Context**: The `TenantMiddleware` only set tenant context for URLs starting with `/app/`, leaving users logging in through `/accounts/login/` without tenant information.

2. **Circular Redirect Logic**: `HomePageView` and `CustomLoginView` had conflicting redirect logic that could create loops when tenant context was missing.

3. **Inadequate Error Handling**: Missing tenant scenarios resulted in redirects that would trigger more redirects instead of showing clear error messages.

4. **Middleware Interaction Issues**: Multiple middleware components were not properly handling edge cases where tenant context was missing.

## Fixes Implemented

### 1. Enhanced CustomLoginView (`accounts/views.py`)

**Changes Made:**
- Added `form_valid()` method to set tenant in session after successful login
- Enhanced `get_success_url()` with comprehensive tenant validation
- Added proper error handling for users without tenant assignments
- Implemented safe fallback redirects to prevent loops

**Key Improvements:**
```python
# Set tenant in session after successful login
if hasattr(user, 'tenant') and user.tenant:
    self.request.session['current_tenant_id'] = user.tenant.pk
    self.request.session.save()

# Validate tenant before redirecting
if user.role == 'lawyer':
    if hasattr(user, 'tenant') and user.tenant:
        return reverse_lazy('lawyer_panel:dashboard')
    else:
        # Show error instead of redirecting
        messages.error(self.request, "Your account is not associated with any law firm.")
        return reverse_lazy('home')
```

### 2. Improved HomePageView (`pages/views.py`)

**Changes Made:**
- Added tenant validation before role-based redirects
- Implemented graceful error handling for missing tenant scenarios
- Prevented redirects that could cause loops

**Key Improvements:**
```python
if request.user.role == 'lawyer':
    if hasattr(request.user, 'tenant') and request.user.tenant:
        return redirect('lawyer_panel:dashboard')
    else:
        # Show error message instead of redirecting
        messages.error(request, "Your account is not associated with any law firm.")
        return super().dispatch(request, *args, **kwargs)
```

### 3. Enhanced LawyerPanelRequiredMixin (`lawyer_panel/views.py`)

**Changes Made:**
- Improved tenant detection logic
- Added error template rendering instead of redirects for missing tenant
- Created user-friendly error page for no-tenant scenarios

**Key Improvements:**
```python
if not tenant:
    # Render error page instead of redirecting
    messages.error(request, "Your account is not associated with any law firm.")
    return render(request, 'lawyer_panel/no_tenant_error.html', {
        'user': request.user,
        'title': 'No Tenant Assigned'
    })
```

### 4. Enhanced TenantMiddleware (`tenants/middleware.py`)

**Changes Made:**
- Added session-based tenant detection for login flows
- Improved tenant context persistence across requests
- Better handling of tenant validation and status checks

**Key Improvements:**
```python
# Check session for tenant context (for login flows)
if 'current_tenant_id' in request.session:
    try:
        tenant_id = request.session['current_tenant_id']
        tenant = Tenant.objects.get(pk=tenant_id)
        # Store tenant in session for future requests
        request.session['current_tenant_id'] = tenant.pk
        request.session.save()
        return tenant
    except (Tenant.DoesNotExist, ValueError):
        # Clear invalid tenant from session
        del request.session['current_tenant_id']
```

### 5. Improved SubscriptionMiddleware (`subscriptions/middleware.py`)

**Changes Made:**
- Enhanced tenant detection from multiple sources
- Added skip paths for login/logout URLs
- Prevented subscription checks from interfering with authentication flow

**Key Improvements:**
```python
# Get tenant from request or from user
tenant = getattr(request, 'tenant', None)
if not tenant and hasattr(request.user, 'tenant'):
    tenant = request.user.tenant

# Skip subscription checks for auth URLs
skip_paths = [
    '/subscriptions/',
    '/account/',
    '/admin/',
    '/static/',
    '/media/',
    '/accounts/login/',
    '/accounts/logout/',
]
```

### 6. Added Redirect Loop Detection Middleware (`core/middleware.py`)

**New Features:**
- Detects when same URL is redirected to multiple times
- Automatically breaks redirect loops with safe error pages
- Provides debugging information for troubleshooting
- Tracks redirect count and last redirect URL

**Key Features:**
```python
class RedirectLoopDetectionMiddleware(MiddlewareMixin):
    def __call__(self, request):
        redirect_count = request.session.get('redirect_count', 0)
        last_redirect_url = request.session.get('last_redirect_url', '')
        
        # Detect loop: same URL redirected > 3 times
        if (redirect_count > 3 and 
            current_url == last_redirect_url and 
            request.method == 'GET'):
            
            # Break loop with safe response
            return self._get_safe_response(request)
```

### 7. Added Tenant Context Middleware (`core/middleware.py`)

**New Features:**
- Ensures tenant context is available for all authenticated users
- Sets tenant from user relationship if not already present
- Provides consistent tenant context across the application

## New Templates Created

### 1. No Tenant Error Page (`lawyer_panel/templates/lawyer_panel/no_tenant_error.html`)
- User-friendly error message for users without tenant assignment
- Clear instructions on what to do next
- Professional styling with Bootstrap components

### 2. Redirect Loop Error Page (`core/templates/core/redirect_loop_error.html`)
- Explains what a redirect loop is in simple terms
- Provides actionable steps for users
- Includes sign out and home page options

## Configuration Changes

### Updated Settings (`django_project/settings.py`)

**Middleware Order Updated:**
```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "core.middleware.RedirectLoopDetectionMiddleware",  # NEW: Early detection
    "core.middleware.TenantContextMiddleware",      # NEW: Ensure context
    "tenants.middleware.TenantMiddleware",          # Enhanced
    "subscriptions.middleware.SubscriptionMiddleware",   # Enhanced
    # ... rest of middleware
]
```

**New App Added:**
```python
INSTALLED_APPS = [
    # ... existing apps
    "core",  # NEW: Must be first among local apps
    # ... rest of apps
]
```

## Testing

### Test Script (`test_redirect_fix.py`)

Created comprehensive test script that verifies:
- Login redirects for different user roles
- Tenant middleware functionality
- Home page redirect behavior
- Redirect loop detection
- Error handling for missing tenants

### How to Run Tests

```bash
python test_redirect_fix.py
```

## Benefits of These Fixes

1. **Prevents Redirect Loops**: Multiple layers of protection against infinite redirects
2. **Better Error Handling**: Clear, user-friendly error messages instead of confusing redirects
3. **Improved Tenant Context**: Consistent tenant handling across all parts of the application
4. **Enhanced Debugging**: Better logging and error tracking for troubleshooting
5. **Graceful Degradation**: System continues to work even when some components fail

## Deployment Instructions

1. **Deploy Code Changes**: All modified files should be deployed together
2. **Run Migrations**: No database migrations are required for these changes
3. **Clear Cache**: Clear any cached redirects or sessions
4. **Test Thoroughly**: Use the provided test script to verify fixes
5. **Monitor Logs**: Watch for any redirect-related warnings in the logs

## Troubleshooting

If users still experience redirect issues after these fixes:

1. **Check Browser**: Clear browser cache, cookies, and session data
2. **Verify User Setup**: Ensure users have proper tenant assignments
3. **Check Middleware Order**: Verify middleware is loaded in correct order
4. **Review Logs**: Check for any redirect loop warnings in application logs
5. **Test Isolated**: Use the test script to reproduce issues in controlled environment

## Future Improvements

1. **Add Unit Tests**: Create automated tests for all redirect scenarios
2. **Enhanced Monitoring**: Add metrics for redirect frequency and patterns
3. **User Dashboard**: Add admin panel to monitor and fix redirect issues
4. **Automatic Recovery**: Implement automatic tenant assignment for orphaned users