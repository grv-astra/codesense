from django.db import models
from common.orm import UUIDModel


class User(UUIDModel):
    email = models.CharField(max_length=255, db_index=True)
    password = models.CharField(max_length=255)
    name = models.CharField(max_length=255, blank=True, default="")
    company = models.CharField(max_length=255, null=True, blank=True)
    role = models.CharField(max_length=50, default="User")
    deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        app_label = "auth_app"
        db_table = "users"


class RolePermission(models.Model):
    role = models.CharField(max_length=50, unique=True)
    permissions = models.JSONField(default=dict)
    updated_at = models.DateTimeField()

    class Meta:
        app_label = "auth_app"
        db_table = "permissions"
