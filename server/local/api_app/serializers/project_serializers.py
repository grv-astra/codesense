# projects/serializers.py
from rest_framework import serializers

class ProjectCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    preset = serializers.CharField()
    description = serializers.CharField(allow_blank=True)

class ProjectUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    preset = serializers.CharField(required=False)
    description = serializers.CharField(required=False)
    deleted = serializers.BooleanField(required=False)
