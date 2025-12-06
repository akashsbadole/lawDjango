/**
 * HTMX and Alpine.js Integration for Lawyer Management System
 * This file provides common functionality and initialization for both libraries
 */

// Initialize HTMX configuration
document.addEventListener('htmx:configRequest', function(evt) {
    // Add CSRF token to all HTMX requests
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfToken) {
        evt.detail.parameters['csrfmiddlewaretoken'] = csrfToken.value;
    }
    
    // Add tenant context if available
    const tenantId = document.body.dataset.tenantId;
    if (tenantId) {
        evt.detail.parameters['tenant_id'] = tenantId;
    }
});

// HTMX event handlers
document.addEventListener('htmx:beforeRequest', function(evt) {
    // Show loading state
    const target = evt.target;
    if (target.classList) {
        target.classList.add('loading');
    }
    
    // Disable buttons during request
    const buttons = target.querySelectorAll('button, input[type="submit"]');
    buttons.forEach(btn => {
        btn.disabled = true;
        btn.dataset.originalText = btn.textContent;
        btn.textContent = 'Loading...';
    });
});

document.addEventListener('htmx:afterRequest', function(evt) {
    // Remove loading state
    const target = evt.target;
    if (target.classList) {
        target.classList.remove('loading');
    }
    
    // Re-enable buttons
    const buttons = target.querySelectorAll('button, input[type="submit"]');
    buttons.forEach(btn => {
        btn.disabled = false;
        if (btn.dataset.originalText) {
            btn.textContent = btn.dataset.originalText;
            delete btn.dataset.originalText;
        }
    });
    
    // Re-initialize Alpine components for dynamically loaded content
    if (window.Alpine) {
        window.Alpine.initTree(target);
    }
});

document.addEventListener('htmx:responseError', function(evt) {
    // Handle error responses
    console.error('HTMX request failed:', evt.detail);
    
    // Show error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger alert-dismissible fade show';
    errorDiv.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="fas fa-exclamation-triangle me-2"></i>
            <div class="flex-grow-1">
                An error occurred while processing your request. Please try again.
            </div>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
    
    // Insert error message at the top of the target element
    const target = evt.target;
    target.insertBefore(errorDiv, target.firstChild);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.parentNode.removeChild(errorDiv);
        }
    }, 5000);
});

// Alpine.js data and methods
document.addEventListener('alpine:init', () => {
    // Global Alpine data
    Alpine.data('app', () => ({
        // Theme management
        darkMode: false,
        
        init() {
            // Initialize dark mode from localStorage
            this.darkMode = localStorage.getItem('darkMode') === 'true';
            this.updateTheme();
        },
        
        toggleDarkMode() {
            this.darkMode = !this.darkMode;
            localStorage.setItem('darkMode', this.darkMode);
            this.updateTheme();
        },
        
        updateTheme() {
            if (this.darkMode) {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }
        },
        
        // Mobile menu
        mobileMenuOpen: false,
        
        toggleMobileMenu() {
            this.mobileMenuOpen = !this.mobileMenuOpen;
        },
        
        // Search functionality
        searchQuery: '',
        searchResults: [],
        
        async performSearch() {
            if (this.searchQuery.length < 2) {
                this.searchResults = [];
                return;
            }
            
            try {
                const response = await fetch(`/api/search/?q=${encodeURIComponent(this.searchQuery)}`);
                const data = await response.json();
                this.searchResults = data.results || [];
            } catch (error) {
                console.error('Search failed:', error);
                this.searchResults = [];
            }
        },
        
        // Form helpers
        isSubmitting: false,
        
        async submitForm(formElement) {
            if (this.isSubmitting) return;
            
            this.isSubmitting = true;
            const formData = new FormData(formElement);
            
            try {
                const response = await fetch(formElement.action, {
                    method: formElement.method,
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                });
                
                if (response.ok) {
                    // Handle successful submission
                    const result = await response.json();
                    if (result.redirect) {
                        window.location.href = result.redirect;
                    } else if (result.message) {
                        this.showNotification(result.message, 'success');
                    }
                } else {
                    // Handle errors
                    const error = await response.json();
                    this.showNotification(error.message || 'An error occurred', 'error');
                }
            } catch (error) {
                console.error('Form submission failed:', error);
                this.showNotification('Network error. Please try again.', 'error');
            } finally {
                this.isSubmitting = false;
            }
        },
        
        // Notification system
        notifications: [],
        
        showNotification(message, type = 'info') {
            const id = Date.now();
            this.notifications.push({ id, message, type });
            
            // Auto-remove after 5 seconds
            setTimeout(() => {
                this.notifications = this.notifications.filter(n => n.id !== id);
            }, 5000);
        },
        
        removeNotification(id) {
            this.notifications = this.notifications.filter(n => n.id !== id);
        }
    }));
    
    // Modal component
    Alpine.data('modal', (initialOpen = false) => ({
        open: initialOpen,
        
        show() {
            this.open = true;
            document.body.style.overflow = 'hidden';
        },
        
        hide() {
            this.open = false;
            document.body.style.overflow = '';
        },
        
        toggle() {
            this.open = !this.open;
            document.body.style.overflow = this.open ? 'hidden' : '';
        }
    }));
    
    // Dropdown component
    Alpine.data('dropdown', (initialOpen = false) => ({
        open: initialOpen,
        
        toggle() {
            this.open = !this.open;
        },
        
        close() {
            this.open = false;
        }
    }));
    
    // Tabs component
    Alpine.data('tabs', (initialTab = 0) => ({
        activeTab: initialTab,
        
        setActiveTab(index) {
            this.activeTab = index;
        }
    }));
});

// Utility functions
window.LawyerApp = {
    // Show loading spinner
    showLoading(element) {
        if (element) {
            element.classList.add('loading');
        }
    },
    
    // Hide loading spinner
    hideLoading(element) {
        if (element) {
            element.classList.remove('loading');
        }
    },
    
    // Show confirmation dialog
    confirm(message, callback) {
        if (confirm(message)) {
            callback();
        }
    },
    
    // Format date
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    },
    
    // Format currency
    formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(amount);
    },
    
    // Debounce function
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Add CSRF token to all forms if not present
    const forms = document.querySelectorAll('form:not([method="GET"])');
    forms.forEach(form => {
        if (!form.querySelector('[name=csrfmiddlewaretoken]')) {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
            if (csrfToken) {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'csrfmiddlewaretoken';
                input.value = csrfToken.value;
                form.appendChild(input);
            }
        }
    });
    
    // Initialize tooltips if Bootstrap is available
    if (window.bootstrap && window.bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
});