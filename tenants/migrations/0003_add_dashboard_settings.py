# Generated migration for adding dashboard settings to TenantSettings

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0002_tenantsettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenantsettings',
            name='dashboard_widgets',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='List of default dashboard widgets for this tenant (JSON format)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsettings',
            name='dashboard_layout',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Default dashboard layout configuration (JSON format)'
            ),
        ),
        migrations.AddField(
            model_name='tenantsettings',
            name='dashboard_date_range_days',
            field=models.IntegerField(
                default=30,
                help_text='Default date range for dashboard widgets (in days)',
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(365)
                ],
            ),
        ),
        migrations.AddField(
            model_name='tenantsettings',
            name='dashboard_auto_refresh',
            field=models.BooleanField(
                default=True,
                help_text='Enable auto-refresh for dashboard widgets'
            ),
        ),
        migrations.AddField(
            model_name='tenantsettings',
            name='dashboard_auto_refresh_interval',
            field=models.IntegerField(
                default=300,
                help_text='Auto-refresh interval in seconds',
                validators=[
                    django.core.validators.MinValueValidator(30),
                    django.core.validators.MaxValueValidator(3600)
                ],
            ),
        ),
    ]