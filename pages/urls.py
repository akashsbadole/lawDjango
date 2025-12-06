from django.urls import path

from .views import (
    HomePageView, AboutPageView, FeaturesPageView, PricingPageView,
    ContactPageView, BlogPageView, PrivacyPageView, TermsPageView,
    TestimonialsPageView, FAQPageView, SecurityPageView, AuthPageView,
    DemoPageView
)

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("features/", FeaturesPageView.as_view(), name="features"),
    path("pricing/", PricingPageView.as_view(), name="pricing"),
    path("contact/", ContactPageView.as_view(), name="contact"),
    path("blog/", BlogPageView.as_view(), name="blog"),
    path("privacy/", PrivacyPageView.as_view(), name="privacy"),
    path("terms/", TermsPageView.as_view(), name="terms"),
    path("testimonials/", TestimonialsPageView.as_view(), name="testimonials"),
    path("faq/", FAQPageView.as_view(), name="faq"),
    path("security/", SecurityPageView.as_view(), name="security"),
    path("auth/", AuthPageView.as_view(), name="auth"),
    path("demo/", DemoPageView.as_view(), name="demo"),
]
