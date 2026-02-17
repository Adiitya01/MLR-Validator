from rest_framework import serializers
from .models import ValidationJob

class ValidationJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValidationJob
        fields = '__all__'
        read_only_fields = ('id', 'user', 'status', 'result_json', 'created_at', 'completed_at', 'error_message')

class UploadSerializer(serializers.Serializer):
    brochure_pdf = serializers.FileField()
    reference_pdfs = serializers.ListField(
        child=serializers.FileField(),
        allow_empty=False
    )
    validation_type = serializers.ChoiceField(choices=['research', 'drug'], default='research')
