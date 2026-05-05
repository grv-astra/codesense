# projects/serializers.py
from rest_framework import serializers

class ProjectCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)

class ProjectUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    description = serializers.CharField(required=False)
