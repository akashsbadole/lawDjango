from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin


class HomePageView(TemplateView):
    template_name = "pages/home.html"
    
    def dispatch(self, request, *args, **kwargs):
        # If user is authenticated, redirect based on role
        if request.user.is_authenticated:
            # Check if user has a role attribute
            if hasattr(request.user, 'role'):
                if request.user.role == 'lawyer':
                    # Check if lawyer has a tenant before redirecting
                    if hasattr(request.user, 'tenant') and request.user.tenant:
                        return redirect('lawyer_panel:dashboard')
                    else:
                        # Lawyer without tenant - show error message
                        from django.contrib import messages
                        messages.error(
                            request,
                            "Your account is not associated with any law firm. "
                            "Please contact your administrator."
                        )
                        return super().dispatch(request, *args, **kwargs)
                        
                elif request.user.role == 'admin':
                    # Check if admin has a tenant
                    if hasattr(request.user, 'tenant') and request.user.tenant:
                        return redirect('tenant-dashboard', slug=request.user.tenant.slug)
                    else:
                        # Admin without tenant - redirect to admin panel
                        return redirect('admin:index')
                        
                elif request.user.role == 'platform_admin':
                    return redirect('platform_admin:dashboard')
        
        # For unauthenticated users or users without specific roles, show home page
        return super().dispatch(request, *args, **kwargs)


class AboutPageView(TemplateView):
    template_name = "pages/about.html"


class FeaturesPageView(TemplateView):
    template_name = "pages/features.html"


class PricingPageView(TemplateView):
    template_name = "pages/pricing.html"


class ContactPageView(TemplateView):
    template_name = "pages/contact.html"


class BlogPageView(TemplateView):
    template_name = "pages/blog.html"


class PrivacyPageView(TemplateView):
    template_name = "pages/privacy.html"


class TermsPageView(TemplateView):
    template_name = "pages/terms.html"


class TestimonialsPageView(TemplateView):
    template_name = "pages/testimonials.html"


class FAQPageView(TemplateView):
    template_name = "pages/faq.html"


class SecurityPageView(TemplateView):
    template_name = "pages/security.html"


class AuthPageView(TemplateView):
    template_name = "pages/auth.html"


class DemoPageView(TemplateView):
    template_name = "pages/demo.html"
