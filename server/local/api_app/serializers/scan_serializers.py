# projects/serializers.py
from rest_framework import serializers

class ScanStartSerializer(serializers.Serializer):
    scan_name = serializers.CharField(required=True)
    project_id = serializers.CharField(required=True)
    zip_file = serializers.FileField(required=True)

class ScanWithSbomSerializer(serializers.Serializer):
    scan_name = serializers.CharField(required= True)
    project_id = serializers.CharField(required=True)
    sbom_file = serializers.FileField(required=True)

class ScanProgressSerializer(serializers.Serializer):
    total_files = serializers.IntegerField()
    scanned_files = serializers.IntegerField()
    percentage_completed = serializers.FloatField()
    status = serializers.CharField(allow_blank=True, required=False)
    severity_counts = serializers.DictField(child=serializers.IntegerField())
