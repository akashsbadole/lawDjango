from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='users'
    )
    role = models.CharField(
        max_length=50,
        default='lawyer',
        choices=[
            ('admin', 'Admin'),
            ('lawyer', 'Lawyer'),
            ('paralegal', 'Paralegal'),
            ('billing_manager', 'Billing Manager'),
            ('staff', 'Staff'),
        ]
    )

    def __str__(self):
        return self.email