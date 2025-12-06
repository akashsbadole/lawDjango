/**
 * Backup & Restore Module JavaScript
 * Handles interactive features for backup and restore operations
 */

// Global variables
let backupProgressInterval = null;
let restoreProgressInterval = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  initializeBackupRestore();
});

/**
 * Initialize backup and restore functionality
 */
function initializeBackupRestore() {
  // Initialize tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  // Initialize file upload areas
  initializeFileUpload();
  
  // Initialize progress tracking
  initializeProgressTracking();
  
  // Initialize schedule toggles
  initializeScheduleToggles();
  
  // Initialize backup wizard
  initializeBackupWizard();
  
  // Initialize restore wizard
  initializeRestoreWizard();
}

/**
 * Initialize file upload areas with drag and drop
 */
function initializeFileUpload() {
  const uploadAreas = document.querySelectorAll('.upload-area');
  
  uploadAreas.forEach(area => {
    const fileInput = area.querySelector('input[type="file"]');
    
    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      area.addEventListener(eventName, preventDefaults, false);
    });
    
    // Highlight drop area when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
      area.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
      area.addEventListener(eventName, unhighlight, false);
    });
    
    // Handle dropped files
    area.addEventListener('drop', handleDrop, false);
    
    // Handle file selection
    if (fileInput) {
      fileInput.addEventListener('change', function() {
        handleFiles(this.files);
      });
    }
  });
}

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

function highlight(e) {
  this.classList.add('dragover');
}

function unhighlight(e) {
  this.classList.remove('dragover');
}

function handleDrop(e) {
  const dt = e.dataTransfer;
  const files = dt.files;
  handleFiles(files);
}

function handleFiles(files) {
  if (files.length > 0) {
    const file = files[0];
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
      fileInput.files = files;
      
      // Update UI to show selected file
      const fileName = document.querySelector('.selected-file-name');
      if (fileName) {
        fileName.textContent = file.name;
      }
      
      // Validate file
      validateBackupFile(file);
    }
  }
}

/**
 * Validate backup file
 */
function validateBackupFile(file) {
  const validExtensions = ['.tar.gz', '.zip', '.sql'];
  const fileName = file.name.toLowerCase();
  const isValidExtension = validExtensions.some(ext => fileName.endsWith(ext));
  
  if (!isValidExtension) {
    showAlert('Invalid file format. Please select a valid backup file (.tar.gz, .zip, .sql)', 'danger');
    return false;
  }
  
  // Check file size (limit to 1GB for web upload)
  const maxSize = 1024 * 1024 * 1024; // 1GB
  if (file.size > maxSize) {
    showAlert('File too large. Maximum size is 1GB for web upload.', 'danger');
    return false;
  }
  
  return true;
}

/**
 * Initialize progress tracking for long-running operations
 */
function initializeProgressTracking() {
  // Find running operations and start tracking
  const runningBackups = document.querySelectorAll('.backup-running');
  const runningRestores = document.querySelectorAll('.restore-running');
  
  runningBackups.forEach(backup => {
    const backupId = backup.dataset.backupId;
    startBackupProgressTracking(backupId);
  });
  
  runningRestores.forEach(restore => {
    const restoreId = restore.dataset.restoreId;
    startRestoreProgressTracking(restoreId);
  });
}

/**
 * Start tracking backup progress
 */
function startBackupProgressTracking(backupId) {
  if (backupProgressInterval) {
    clearInterval(backupProgressInterval);
  }
  
  backupProgressInterval = setInterval(() => {
    fetch(`/backup-restore/api/backup/${backupId}/progress/`)
      .then(response => response.json())
      .then(data => {
        updateBackupProgress(backupId, data);
        
        // Stop tracking if completed
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
          clearInterval(backupProgressInterval);
        }
      })
      .catch(error => {
        console.error('Error fetching backup progress:', error);
      });
  }, 3000); // Update every 3 seconds
}

/**
 * Start tracking restore progress
 */
function startRestoreProgressTracking(restoreId) {
  if (restoreProgressInterval) {
    clearInterval(restoreProgressInterval);
  }
  
  restoreProgressInterval = setInterval(() => {
    fetch(`/backup-restore/api/restore/${restoreId}/progress/`)
      .then(response => response.json())
      .then(data => {
        updateRestoreProgress(restoreId, data);
        
        // Stop tracking if completed
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
          clearInterval(restoreProgressInterval);
        }
      })
      .catch(error => {
        console.error('Error fetching restore progress:', error);
      });
  }, 3000); // Update every 3 seconds
}

/**
 * Update backup progress in UI
 */
function updateBackupProgress(backupId, data) {
  const progressBar = document.querySelector(`#backup-progress-${backupId}`);
  const statusBadge = document.querySelector(`#backup-status-${backupId}`);
  const currentStep = document.querySelector(`#backup-step-${backupId}`);
  
  if (progressBar) {
    progressBar.style.width = `${data.progress_percentage}%`;
    progressBar.setAttribute('aria-valuenow', data.progress_percentage);
    progressBar.textContent = `${data.progress_percentage}%`;
  }
  
  if (statusBadge) {
    statusBadge.className = `badge ${getStatusBadgeClass(data.status)}`;
    statusBadge.textContent = data.status_display;
  }
  
  if (currentStep && data.current_step) {
    currentStep.textContent = data.current_step;
  }
}

/**
 * Update restore progress in UI
 */
function updateRestoreProgress(restoreId, data) {
  const progressBar = document.querySelector(`#restore-progress-${restoreId}`);
  const statusBadge = document.querySelector(`#restore-status-${restoreId}`);
  const currentStep = document.querySelector(`#restore-step-${restoreId}`);
  const recordsRestored = document.querySelector(`#records-restored-${restoreId}`);
  
  if (progressBar) {
    progressBar.style.width = `${data.progress_percentage}%`;
    progressBar.setAttribute('aria-valuenow', data.progress_percentage);
    progressBar.textContent = `${data.progress_percentage}%`;
  }
  
  if (statusBadge) {
    statusBadge.className = `badge ${getStatusBadgeClass(data.status)}`;
    statusBadge.textContent = data.status_display;
  }
  
  if (currentStep && data.current_step) {
    currentStep.textContent = data.current_step;
  }
  
  if (recordsRestored && data.records_restored) {
    recordsRestored.textContent = data.records_restored;
  }
}

/**
 * Get status badge class based on status
 */
function getStatusBadgeClass(status) {
  switch (status) {
    case 'completed':
      return 'bg-success';
    case 'running':
      return 'bg-primary';
    case 'failed':
      return 'bg-danger';
    case 'cancelled':
      return 'bg-warning';
    case 'pending':
      return 'bg-secondary';
    default:
      return 'bg-secondary';
  }
}

/**
 * Initialize schedule toggles
 */
function initializeScheduleToggles() {
  const toggles = document.querySelectorAll('.schedule-toggle input[type="checkbox"]');
  
  toggles.forEach(toggle => {
    toggle.addEventListener('change', function() {
      const scheduleId = this.dataset.scheduleId;
      const isActive = this.checked;
      
      updateScheduleStatus(scheduleId, isActive);
    });
  });
}

/**
 * Update schedule status via API
 */
function updateScheduleStatus(scheduleId, isActive) {
  const url = `/backup-restore/api/schedule/${scheduleId}/toggle/`;
  
  fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken')
    },
    body: JSON.stringify({ is_active: isActive })
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert('Schedule status updated successfully', 'success');
    } else {
      showAlert('Failed to update schedule status', 'danger');
    }
  })
  .catch(error => {
    console.error('Error updating schedule status:', error);
    showAlert('An error occurred while updating schedule status', 'danger');
  });
}

/**
 * Initialize backup wizard
 */
function initializeBackupWizard() {
  const wizardForms = document.querySelectorAll('.backup-wizard-form');
  
  wizardForms.forEach(form => {
    const steps = form.querySelectorAll('.wizard-step');
    const nextButtons = form.querySelectorAll('.wizard-next');
    const prevButtons = form.querySelectorAll('.wizard-prev');
    
    // Handle next button clicks
    nextButtons.forEach(button => {
      button.addEventListener('click', function() {
        const currentStep = parseInt(this.dataset.currentStep);
        const nextStep = currentStep + 1;
        
        if (validateWizardStep(form, currentStep)) {
          showWizardStep(form, nextStep);
        }
      });
    });
    
    // Handle previous button clicks
    prevButtons.forEach(button => {
      button.addEventListener('click', function() {
        const currentStep = parseInt(this.dataset.currentStep);
        const prevStep = currentStep - 1;
        
        showWizardStep(form, prevStep);
      });
    });
  });
}

/**
 * Initialize restore wizard
 */
function initializeRestoreWizard() {
  const wizardForms = document.querySelectorAll('.restore-wizard-form');
  
  wizardForms.forEach(form => {
    const steps = form.querySelectorAll('.wizard-step');
    const nextButtons = form.querySelectorAll('.wizard-next');
    const prevButtons = document.querySelectorAll('.wizard-prev');
    
    // Handle next button clicks
    nextButtons.forEach(button => {
      button.addEventListener('click', function() {
        const currentStep = parseInt(this.dataset.currentStep);
        const nextStep = currentStep + 1;
        
        if (validateRestoreWizardStep(form, currentStep)) {
          showWizardStep(form, nextStep);
        }
      });
    });
    
    // Handle previous button clicks
    prevButtons.forEach(button => {
      button.addEventListener('click', function() {
        const currentStep = parseInt(this.dataset.currentStep);
        const prevStep = currentStep - 1;
        
        showWizardStep(form, prevStep);
      });
    });
  });
}

/**
 * Show specific wizard step
 */
function showWizardStep(form, stepIndex) {
  const steps = form.querySelectorAll('.wizard-step');
  const stepIndicators = form.querySelectorAll('.wizard-step-indicator');
  
  // Hide all steps
  steps.forEach((step, index) => {
    step.style.display = index === stepIndex ? 'block' : 'none';
  });
  
  // Update indicators
  stepIndicators.forEach((indicator, index) => {
    if (index < stepIndex) {
      indicator.classList.add('completed');
      indicator.classList.remove('active');
    } else if (index === stepIndex) {
      indicator.classList.add('active');
      indicator.classList.remove('completed');
    } else {
      indicator.classList.remove('active', 'completed');
    }
  });
}

/**
 * Validate current wizard step
 */
function validateWizardStep(form, stepIndex) {
  const currentStepElement = form.querySelector(`.wizard-step[data-step="${stepIndex}"]`);
  const requiredFields = currentStepElement.querySelectorAll('[required]');
  
  let isValid = true;
  requiredFields.forEach(field => {
    if (!field.value.trim()) {
      field.classList.add('is-invalid');
      isValid = false;
    } else {
      field.classList.remove('is-invalid');
    }
  });
  
  if (!isValid) {
    showAlert('Please fill in all required fields', 'warning');
  }
  
  return isValid;
}

/**
 * Validate restore wizard step
 */
function validateRestoreWizardStep(form, stepIndex) {
  // Special validation for restore wizard
  if (stepIndex === 0) {
    // Check if backup source is selected
    const backupJob = form.querySelector('[name="backup_job"]');
    const backupFile = form.querySelector('[name="backup_file"]');
    
    if (!backupJob.value && !backupFile.files.length) {
      showAlert('Please select a backup source', 'warning');
      return false;
    }
  }
  
  return validateWizardStep(form, stepIndex);
}

/**
 * Run backup schedule immediately
 */
function runScheduleNow(scheduleId) {
  if (confirm('Are you sure you want to run this backup schedule now?')) {
    const url = `/backup-restore/api/schedule/${scheduleId}/run-now/`;
    
    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      }
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        showAlert('Backup job created successfully', 'success');
        // Redirect to backup job detail page
        window.location.href = `/backup-restore/backup/${data.backup_job_id}/`;
      } else {
        showAlert('Failed to create backup job', 'danger');
      }
    })
    .catch(error => {
      console.error('Error creating backup job:', error);
      showAlert('An error occurred while creating backup job', 'danger');
    });
  }
}

/**
 * Show alert message
 */
function showAlert(message, type) {
  const alertDiv = document.createElement('div');
  alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
  alertDiv.setAttribute('role', 'alert');
  alertDiv.innerHTML = `
    ${message}
    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
  `;
  
  // Insert at top of main content area
  const mainContent = document.querySelector('main') || document.querySelector('.container');
  if (mainContent) {
    mainContent.insertBefore(alertDiv, mainContent.firstChild);
  }
  
  // Auto-remove after 5 seconds
  setTimeout(() => {
    if (alertDiv.parentNode) {
      alertDiv.parentNode.removeChild(alertDiv);
    }
  }, 5000);
}

/**
 * Get CSRF token from cookies
 */
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

/**
 * Format file size for display
 */
function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Format duration for display
 */
function formatDuration(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`;
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  } else {
    return `${secs}s`;
  }
}

// Export functions for global access
window.backupRestore = {
  runScheduleNow,
  updateScheduleStatus,
  showAlert,
  formatFileSize,
  formatDuration
};