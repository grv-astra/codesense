import uuid
from django.db import models


def new_uuid_hex() -> str:
    return uuid.uuid4().hex


class UUIDModel(models.Model):
    """Abstract base: 32-char uuid-hex string primary key, exposed as `id`."""

    id = models.CharField(primary_key=True, max_length=32, default=new_uuid_hex, editable=False)

    class Meta:
        abstract = True
