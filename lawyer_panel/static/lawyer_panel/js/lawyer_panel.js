// Lawyer Panel JavaScript

// DOM Ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    initializeTooltips();
    
    // Initialize sidebar toggle
    initializeSidebarToggle();
    
    // Initialize data tables
    initializeDataTables();
    
    // Initialize confirmations
    initializeConfirmations();
});

// Initialize Bootstrap Tooltips
function initializeTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            boundary: 'viewport',
            trigger: 'hover focus'
        });
    });
    
    tooltipList.forEach(function (tooltip) {
        tooltip.show();
    });
}

// Initialize Sidebar Toggle
function initializeSidebarToggle() {
    var sidebarToggle = document.getElementById('sidebarToggle');
    var sidebarToggleTop = document.getElementById('sidebarToggleTop');
    
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function(e) {
            e.preventDefault();
            document.body.classList.toggle('sidebar-collapsed');
            localStorage.setItem('sidebar|toggle', document.body.classList.contains('sidebar-collapsed'));
        });
    }
    
    if (sidebarToggleTop) {
        sidebarToggleTop.addEventListener('click', function(e) {
            e.preventDefault();
            document.body.classList.toggle('sidebar-collapsed');
            localStorage.setItem('sidebar|toggle', document.body.classList.contains('sidebar-collapsed'));
        });
    }
    
    // Restore sidebar state from localStorage
    var sidebarState = localStorage.getItem('sidebar|toggle');
    if (sidebarState === 'true') {
        document.body.classList.add('sidebar-collapsed');
    }
}

// Initialize Data Tables
function initializeDataTables() {
    var dataTables = document.querySelectorAll('#dataTable');
    
    dataTables.forEach(function(table) {
        // Simple sorting functionality
        var headers = table.querySelectorAll('th');
        headers.forEach(function(header, index) {
            if (header.textContent.trim() !== 'Actions') {
                header.style.cursor = 'pointer';
                header.addEventListener('click', function() {
                    sortTable(table, index);
                });
                
                // Add sort indicator
                var sortIcon = document.createElement('i');
                sortIcon.className = 'fas fa-sort ml-2';
                header.appendChild(sortIcon);
            }
        });
    });
}

// Table Sorting Function
function sortTable(table, columnIndex) {
    var tbody = table.querySelector('tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));
    var isAscending = table.getAttribute('data-sort-order') !== 'asc';
    
    rows.sort(function(a, b) {
        var aValue = a.children[columnIndex].textContent.trim();
        var bValue = b.children[columnIndex].textContent.trim();
        
        if (isAscending) {
            return aValue.localeCompare(bValue);
        } else {
            return bValue.localeCompare(aValue);
        }
    });
    
    // Clear existing rows
    while (tbody.firstChild) {
        tbody.removeChild(tbody.firstChild);
    }
    
    // Add sorted rows
    rows.forEach(function(row) {
        tbody.appendChild(row);
    });
    
    // Toggle sort order
    table.setAttribute('data-sort-order', isAscending ? 'desc' : 'asc');
    
    // Update sort icons
    var headers = table.querySelectorAll('th');
    headers.forEach(function(header, index) {
        var icon = header.querySelector('i');
        if (icon) {
            if (index === columnIndex) {
                icon.className = 'fas fa-sort-' + (isAscending ? 'up' : 'down') + ' ml-2';
            } else {
                icon.className = 'fas fa-sort ml-2';
            }
        }
    });
}

// Initialize Confirmations
function initializeConfirmations() {
    var deleteButtons = document.querySelectorAll('.delete-confirm');
    
    deleteButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            var itemName = button.getAttribute('data-item-name');
            var itemType = button.getAttribute('data-item-type');
            
            if (confirm('Are you sure you want to delete this ' + itemType + ': ' + itemName + '?')) {
                // Submit the form
                var form = button.closest('form');
                if (form) {
                    form.submit();
                }
            }
        });
    });
}

// Enhanced Confirmation Dialog
function confirm(message) {
    // Create custom confirmation dialog
    var modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Confirm Action</h5>
                    <button type="button" class="btn-close" data-dismiss="modal">&times;</button>
                </div>
                <div class="modal-body">
                    <p>${message}</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-danger confirm-delete">Delete</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Show modal
    setTimeout(function() {
        modal.classList.add('show');
        modal.style.display = 'block';
    }, 10);
    
    return new Promise(function(resolve) {
        var confirmButton = modal.querySelector('.confirm-delete');
        var cancelButton = modal.querySelector('.btn-secondary');
        var closeButton = modal.querySelector('.btn-close');
        
        function cleanup() {
            document.body.removeChild(modal);
        }
        
        confirmButton.addEventListener('click', function() {
            cleanup();
            resolve(true);
        });
        
        cancelButton.addEventListener('click', function() {
            cleanup();
            resolve(false);
        });
        
        closeButton.addEventListener('click', function() {
            cleanup();
            resolve(false);
        });
        
        // Close on backdrop click
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                cleanup();
                resolve(false);
            }
        });
    });
}

// Form Validation
function validateForm(formElement) {
    var inputs = formElement.querySelectorAll('input[required], select[required], textarea[required]');
    var isValid = true;
    
    inputs.forEach(function(input) {
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
            
            // Add error message
            var errorDiv = input.parentNode.querySelector('.invalid-feedback');
            if (!errorDiv) {
                errorDiv = document.createElement('div');
                errorDiv.className = 'invalid-feedback';
                errorDiv.textContent = 'This field is required.';
                input.parentNode.appendChild(errorDiv);
            }
        } else {
            input.classList.remove('is-invalid');
            var errorDiv = input.parentNode.querySelector('.invalid-feedback');
            if (errorDiv) {
                input.parentNode.removeChild(errorDiv);
            }
        }
    });
    
    return isValid;
}

// Auto-resize textareas
function autoResizeTextareas() {
    var textareas = document.querySelectorAll('textarea');
    
    textareas.forEach(function(textarea) {
        textarea.addEventListener('input', function() {
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        });
    });
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    var k = 1024;
    var sizes = ['Bytes', 'KB', 'MB', 'GB'];
    var i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

// Format date
function formatDate(dateString) {
    var date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Search functionality
function initializeSearch() {
    var searchInput = document.querySelector('.search-input');
    var searchResults = document.querySelector('.search-results');
    
    if (searchInput && searchResults) {
        var searchTimeout;
        
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            
            searchTimeout = setTimeout(function() {
                var query = searchInput.value.trim();
                
                if (query.length > 2) {
                    performSearch(query);
                } else {
                    clearSearchResults();
                }
            }, 300);
        });
    }
}

function performSearch(query) {
    // This would make an AJAX call in a real implementation
    console.log('Searching for:', query);
    
    // Show loading state
    var searchResults = document.querySelector('.search-results');
    if (searchResults) {
        searchResults.innerHTML = '<div class="text-center p-3"><i class="fas fa-spinner fa-spin"></i> Searching...</div>';
    }
}

function clearSearchResults() {
    var searchResults = document.querySelector('.search-results');
    if (searchResults) {
        searchResults.innerHTML = '';
    }
}

// Initialize everything when page loads
document.addEventListener('DOMContentLoaded', function() {
    autoResizeTextareas();
    initializeSearch();
});