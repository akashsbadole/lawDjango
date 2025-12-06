from django.shortcuts import redirect
from django.contrib.auth.views import LoginView as BaseLoginView
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponseRedirect


class CustomLoginView(BaseLoginView):
    """Custom login view that redirects users based on their role."""
    
    def form_valid(self, form):
        """Handle successful login with proper tenant context setup."""
        # Call parent's form_valid to handle authentication
        response = super().form_valid(form)
        
        # Set tenant in session if user has a tenant
        user = self.request.user
        if hasattr(user, 'tenant') and user.tenant:
            self.request.session['current_tenant_id'] = user.tenant.pk
            self.request.session.save()  # Ensure session is saved
        
        return response
    
    def get_success_url(self):
        """Return the URL to redirect to after successful login based on user role."""
        user = self.request.user
        
        # Check if user has a role attribute
        if hasattr(user, 'role'):
            if user.role == 'lawyer':
                # Check if lawyer has a tenant before redirecting to lawyer panel
                if hasattr(user, 'tenant') and user.tenant:
                    return reverse_lazy('lawyer_panel:dashboard')
                else:
                    # Lawyer without tenant - show error and redirect to home
                    messages.error(
                        self.request,
                        "Your account is not associated with any law firm. "
                        "Please contact your administrator."
                    )
                    return reverse_lazy('home')
                    
            elif user.role == 'admin':
                # Check if user has a tenant, redirect to tenant dashboard
                if hasattr(user, 'tenant') and user.tenant:
                    return reverse_lazy('tenant-dashboard', kwargs={'slug': user.tenant.slug})
                else:
                    # Admin without tenant - redirect to admin panel
                    return reverse_lazy('admin:index')
                    
            elif user.role == 'platform_admin':
                return reverse_lazy('platform_admin:dashboard')
        
        # Default fallback
        return reverse_lazy('home')
