# Enhanced Tenant Dashboard

This document describes the comprehensive tenant dashboard system implemented for the multi-tenant law firm management system.

## Features

### 1. Dashboard Statistics Widgets
- **Total Clients**: Shows the total number of clients in the system
- **Total Cases**: Displays the total number of cases
- **Total Documents**: Shows the total count of documents
- **Total Invoices**: Displays the total number of invoices
- **Active Cases**: Shows the number of currently active cases
- **Unpaid Invoices**: Displays the count of unpaid invoices (admin/billing managers only)
- **Monthly Revenue**: Shows revenue for the current month (admin/billing managers only)
- **Storage Used**: Displays storage usage in MB
- **User Count**: Shows the number of users in the tenant

### 2. Charts and Visualizations
- **Cases by Type**: Pie chart showing distribution of cases by type
- **Monthly Revenue Trend**: Line chart showing revenue over the last 6 months
- **Case Status Distribution**: Bar chart showing cases by status
- **Document Uploads Over Time**: Line chart showing document uploads over the last 30 days
- **Client Acquisition Chart**: Bar chart showing new clients acquired over the last 6 months

### 3. Recent Activity Feed
- Recent case updates
- New document uploads
- Invoice status changes
- User login activities
- Time entries logged

### 4. Quick Actions Section
- Add new client/case/document/invoice
- Common task shortcuts
- Quick search functionality

### 5. Upcoming Deadlines Widget
- Hearing dates
- Invoice due dates
- Document retention reminders

### 6. Performance Metrics
- Case resolution time
- Client satisfaction (if available)
- Billing efficiency metrics

### 7. Role-Based Dashboard Personalization
- **Admins**: See all widgets and metrics
- **Lawyers**: See their assigned cases and related metrics
- **Billing Managers**: See financial metrics and billing-related widgets
- **Read-only Users**: See limited information based on permissions

### 8. Dashboard Customization
- Widget arrangement (drag and drop)
- Date range filters
- Export functionality for reports
- Auto-refresh settings

### 9. Export Functionality
- Export dashboard data as JSON
- Export dashboard statistics as CSV
- Role-based export permissions

### 10. Responsive Design
- Mobile-friendly layout
- Adaptive widget sizing
- Touch-friendly interactions

### 11. Real-time Updates
- Auto-refresh capability
- HTMX integration for dynamic updates
- Configurable refresh intervals

## Installation and Setup

### 1. Run Migrations
```bash
python manage.py migrate tenants
```

### 2. Create Default Dashboard Widgets
```bash
python manage.py create_default_dashboard_widgets
```

### 3. Update URLs
The dashboard URLs are automatically configured. The enhanced dashboard is available at:
```
/dashboard/<slug:slug>/enhanced/
```

### 4. Configure Tenant Settings
Dashboard settings can be configured in the tenant settings:
- Dashboard widgets
- Dashboard layout
- Default date range
- Auto-refresh settings

## Usage

### Accessing the Dashboard
1. Log in to your tenant
2. Navigate to the dashboard using the sidebar menu or directly at `/dashboard/<tenant-slug>/enhanced/`

### Customizing Your Dashboard
1. Click the "Customize" button on the dashboard
2. Drag and drop widgets to rearrange them
3. Use the available widgets panel to add new widgets
4. Save your changes

### Exporting Dashboard Data
1. Click the "Export" button
2. Choose between JSON or CSV format
3. The exported data will be downloaded

### Filtering Data
1. Use the date range filter to change the time period
2. Configure auto-refresh settings
3. Apply filters to update the dashboard

## Widget Types

### Stats Card Widgets
Display key metrics and statistics with icons and colors.

### Chart Widgets
Visualize data using various chart types (pie, bar, line, doughnut).

### Activity Feed Widgets
Show recent activities and updates across the system.

### Upcoming Deadlines Widgets
Display important dates and deadlines.

### Quick Actions Widgets
Provide shortcuts to common tasks and actions.

### Performance Metrics Widgets
Show key performance indicators and metrics.

## Permissions

The dashboard respects user roles and permissions:
- Widgets can be configured to be visible only to specific roles
- Data is filtered based on user permissions
- Export functionality is role-restricted

## Caching

Dashboard data is cached for performance:
- Default cache time: 5 minutes
- Cache is automatically invalidated when data changes
- Configurable cache settings

## Mobile Support

The dashboard is fully responsive:
- Widgets adapt to screen size
- Touch-friendly interactions
- Optimized for mobile browsers

## Real-time Updates

The dashboard supports real-time updates:
- Configurable auto-refresh intervals
- HTMX integration for dynamic updates
- Efficient data loading

## Technical Implementation

### Models
- `DashboardWidget`: Defines available widget types and configurations
- `UserDashboard`: User-specific dashboard configurations
- `UserDashboardWidget`: Links widgets to user dashboards
- `DashboardActivity`: Tracks user interactions with the dashboard

### Views
- `enhanced_dashboard`: Main dashboard view
- `widget_data`: AJAX endpoint for widget data
- `update_widget_position`: AJAX endpoint for updating widget positions
- `export_dashboard_data`: Export functionality

### Template Tags
- `get_dashboard_widgets`: Get widgets for a user
- `get_widget_data`: Get data for a specific widget
- `get_stats_card_data`: Get data for stats cards
- `get_chart_data`: Get data for charts
- Various filters for formatting and display

### JavaScript Features
- Drag and drop widget arrangement
- Chart.js integration for visualizations
- Sortable.js for widget reordering
- AJAX calls for dynamic updates

## Troubleshooting

### Widgets Not Showing
1. Check user permissions
2. Verify widget visibility settings
3. Clear browser cache

### Charts Not Loading
1. Check browser console for errors
2. Verify Chart.js is loading
3. Check data format in AJAX responses

### Performance Issues
1. Check cache settings
2. Verify database indexes
3. Monitor query performance

## Future Enhancements

Potential future improvements:
- More widget types
- Advanced filtering options
- Custom widget creation
- Dashboard templates
- Integration with external services
- Advanced analytics and reporting