import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
import django.utils.timezone

class User(AbstractUser):
    CUSTOMER = 'CUSTOMER'
    AGENT = 'AGENT'
    ADMIN = 'ADMIN'
    
    ROLE_CHOICES = [
        (CUSTOMER, 'Customer'),
        (AGENT, 'Agent'),
        (ADMIN, 'Admin'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=CUSTOMER)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateTimeField(default=django.utils.timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.username} ({self.role})"
