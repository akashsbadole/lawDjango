# Lawyer Panel Guide

## Overview

The Lawyer Panel is a dedicated interface for lawyers in the multi-tenant Django law firm management system. It provides a streamlined workflow for managing cases, clients, documents, and billing activities.

## Accessing the Lawyer Panel

1. **URL**: `http://localhost:8000/lawyer-panel/`
2. **Authentication**: Users must be logged in with a lawyer role
3. **Tenant Assignment**: Users must be assigned to a tenant

## Features

### 1. Dashboard (`/lawyer-panel/`)
- Overview of active cases, upcoming hearings, and recent activities
- Quick access to time entries and expenses
- Billing summary for the last 30 days
- Quick search functionality

### 2. Case Management (`/lawyer-panel/cases/`)
- **List View**: Filter and search cases by status, type, client
- **Detail View**: View case details, events, documents, time entries, and expenses
- **Create Case**: Add new cases with client assignment
- **Edit Case**: Update case information and status
- **Add Events**: Track case events and hearings

### 3. Client Management (`/lawyer-panel/clients/`)
- **List View**: Search and browse all clients
- **Detail View**: View client information and associated cases
- **Create Client**: Add new clients to the system
- **Edit Client**: Update client contact information

### 4. Document Management (`/lawyer-panel/documents/`)
- **List View**: Filter documents by category, access level, case, or client
- **Detail View**: View document details and download files
- **Upload Documents**: Add new documents with proper categorization
- **Access Control**: Documents respect tenant and user permissions

### 5. Billing & Time Tracking (`/lawyer-panel/billing/`)
- **Billing Dashboard**: Overview of billable hours, billed amounts, and expenses
- **Time Entries**: Log billable and non-billable time
- **Expense Tracking**: Record case-related expenses
- **Financial Summary**: 30-day rolling summary of billing activities

### 6. Time Entries (`/lawyer-panel/time-entries/`)
- List all time entries with filtering options
- Create new time entries linked to cases
- Track billable vs non-billable hours
- Calculate amounts automatically based on rates

### 7. Expenses (`/lawyer-panel/expenses/`)
- Track case-related expenses
- Categorize expenses for reporting
- Link expenses to specific cases
- Monitor expense totals

## Navigation

The lawyer panel features a responsive sidebar navigation with:
- Dashboard
- Cases
- Clients
- Documents
- Billing
- Time Entries
- Expenses

## Security & Tenant Isolation

- **Role-Based Access**: Only users with 'lawyer' or 'admin' roles can access
- **Tenant Isolation**: Users can only see data from their assigned tenant
- **Authentication**: All views require user authentication
- **Permission Checks**: Additional checks for specific actions

## Templates & Styling

The lawyer panel uses:
- **Lithium Template Styling**: Consistent with the rest of the application
- **Bootstrap 5**: Responsive design framework
- **Font Awesome Icons**: Professional iconography
- **Crispy Forms**: Clean form rendering

## Testing

To test the lawyer panel:

1. **Using Test User**:
   - Email: `test@example.com`
   - Password: Check with your administrator
   - Tenant: Test Law Firm

2. **Manual Testing**:
   ```
   1. Start the server: python manage.py runserver
   2. Go to: http://localhost:8000/accounts/login/
   3. Login with valid lawyer credentials
   4. Access: http://localhost:8000/lawyer-panel/
   ```

3. **Automated Testing**:
   ```bash
   python test_lawyer_panel.py
   ```

## File Structure

```
lawyer_panel/
├── __init__.py
├── admin.py
├── apps.py
├── forms.py              # Form definitions
├── models.py             # (Uses existing models from other apps)
├── urls.py              # URL routing
├── views.py             # View classes and functions
└── templates/
    └── lawyer_panel/
        ├── base.html                    # Base template with navigation
        ├── dashboard.html                # Dashboard view
        ├── billing_dashboard.html         # Billing overview
        ├── case_*.html                  # Case management templates
        ├── client_*.html                # Client management templates
        ├── document_*.html              # Document management templates
        ├── time_entry_*.html            # Time entry templates
        ├── expense_*.html               # Expense tracking templates
        └── quick_search_results.html    # Search results
```

## Integration with Existing Apps

The lawyer panel integrates with existing apps:
- **clients**: Client management
- **cases**: Case management and events
- **documents**: Document storage and access
- **billing**: Time entries, expenses, and invoices
- **accounts**: User authentication and roles
- **tenants**: Multi-tenant data isolation

## Customization

To customize the lawyer panel:

1. **Templates**: Modify templates in `lawyer_panel/templates/lawyer_panel/`
2. **Views**: Extend or modify view classes in `lawyer_panel/views.py`
3. **Forms**: Update forms in `lawyer_panel/forms.py`
4. **URLs**: Add new URL patterns in `lawyer_panel/urls.py`
5. **Permissions**: Modify role requirements in `LawyerPanelRequiredMixin`

## Troubleshooting

### Common Issues

1. **302 Redirects**: Normal for unauthenticated users - login required
2. **Permission Denied**: Check user role and tenant assignment
3. **Missing Data**: Ensure tenant has clients, cases, and documents
4. **Template Errors**: Verify template inheritance and context variables

### Debug Tips

- Check user role: `request.user.role`
- Check tenant: `request.tenant`
- Verify model relationships and tenant filtering
- Review middleware order in settings.py

## Future Enhancements

Potential improvements for the lawyer panel:
- Calendar integration for case events
- Document preview functionality
- Advanced reporting and analytics
- Mobile app integration
- Email notifications for case updates
- Invoice generation from time entries
- Document collaboration features