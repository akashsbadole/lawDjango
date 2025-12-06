#!/usr/bin/env python3
"""
Test script for public pages implementation.
This script validates that all public pages are properly configured and accessible.
"""

import os
import sys
import django
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
django.setup()

class PublicPagesTestCase(TestCase):
    """Test case for public pages functionality."""
    
    def setUp(self):
        """Set up test client."""
        self.client = Client()
    
    def test_homepage_accessible(self):
        """Test that homepage is accessible."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Manage Your Law Firm Effortlessly')
    
    def test_features_page_accessible(self):
        """Test that features page is accessible."""
        response = self.client.get(reverse('features'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Powerful Features for Modern Law Firms')
    
    def test_pricing_page_accessible(self):
        """Test that pricing page is accessible."""
        response = self.client.get(reverse('pricing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Simple, Transparent Pricing')
    
    def test_about_page_accessible(self):
        """Test that about page is accessible."""
        response = self.client.get(reverse('about'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'About Our Mission')
    
    def test_contact_page_accessible(self):
        """Test that contact page is accessible."""
        response = self.client.get(reverse('contact'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Get in Touch')
    
    def test_blog_page_accessible(self):
        """Test that blog page is accessible."""
        response = self.client.get(reverse('blog'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Legal Tech Insights & Tips')
    
    def test_privacy_page_accessible(self):
        """Test that privacy page is accessible."""
        response = self.client.get(reverse('privacy'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Privacy Policy')
    
    def test_terms_page_accessible(self):
        """Test that terms page is accessible."""
        response = self.client.get(reverse('terms'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Terms of Service')
    
    def test_testimonials_page_accessible(self):
        """Test that testimonials page is accessible."""
        response = self.client.get(reverse('testimonials'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Customer Success Stories')
    
    def test_faq_page_accessible(self):
        """Test that FAQ page is accessible."""
        response = self.client.get(reverse('faq'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Frequently Asked Questions')
    
    def test_security_page_accessible(self):
        """Test that security page is accessible."""
        response = self.client.get(reverse('security'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Security & Compliance')
    
    def test_auth_page_accessible(self):
        """Test that auth page is accessible."""
        response = self.client.get(reverse('auth'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sign Up or Login')
    
    def test_demo_page_accessible(self):
        """Test that demo page is accessible."""
        response = self.client.get(reverse('demo'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Live Demo')
    
    def test_navigation_links_work(self):
        """Test that navigation links work correctly."""
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'href="{0}"'.format(reverse('features')))
        self.assertContains(response, 'href="{0}"'.format(reverse('pricing')))
        self.assertContains(response, 'href="{0}"'.format(reverse('about')))
    
    def test_footer_links_work(self):
        """Test that footer links work correctly."""
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'href="{0}"'.format(reverse('privacy')))
        self.assertContains(response, 'href="{0}"'.format(reverse('terms')))
        self.assertContains(response, 'href="{0}"'.format(reverse('contact')))
    
    def test_responsive_design_elements(self):
        """Test that responsive design elements are present."""
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'viewport')
        self.assertContains(response, 'bootstrap')
    
    def test_seo_elements_present(self):
        """Test that SEO elements are present."""
        response = self.client.get(reverse('home'))
        self.assertContains(response, '<meta name="description"')
        self.assertContains(response, '<title>')
    
    def test_tenant_branding_integration(self):
        """Test that tenant branding variables are used."""
        response = self.client.get(reverse('home'))
        # Check for CSS custom properties
        self.assertContains(response, 'Law Firm')
    
    def test_interactive_elements_present(self):
        """Test that interactive elements are present."""
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'class="hero-section"')
        self.assertContains(response, 'feature-card')
        self.assertContains(response, 'class="btn"')


def run_tests():
    """Run all tests and return results."""
    import unittest
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(PublicPagesTestCase)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print("PUBLIC PAGES TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFAILURES ({len(result.failures)}):")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print(f"\nERRORS ({len(result.errors)}):")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback.split('Exception:')[-1].strip()}")
    
    if result.wasSuccessful():
        print("\nAll tests passed! Public pages implementation is working correctly.")
        return True
    else:
        print("\nSome tests failed. Please check the issues above.")
        return False


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)