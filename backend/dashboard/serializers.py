from rest_framework import serializers
from .models import SchoolEvent


class SchoolEventSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SchoolEvent
        fields = ['id', 'title', 'date', 'category', 'notes', 'created_by', 'created_by_name', 'created_at']
        read_only_fields = ['created_by', 'created_at']

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else None