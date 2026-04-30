from rest_framework import serializers
from .models import SchoolBranding


class SchoolBrandingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolBranding
        fields = [
            'id', 'school_name', 'logo', 'favicon',
            'primary_color', 'secondary_color', 'accent_color',
            'motto', 'address', 'phone', 'email', 'website',
            'county', 'sub_county', 'ward', 'established_year',
            'knec_code', 'nemis_code', 'school_type', 'curriculum',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_primary_color(self, value):
        return self._validate_hex_color(value)

    def validate_secondary_color(self, value):
        return self._validate_hex_color(value)

    def validate_accent_color(self, value):
        return self._validate_hex_color(value)

    def _validate_hex_color(self, value):
        import re
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
            raise serializers.ValidationError('Must be a valid 6-character hex color (e.g. #1a73e8).')
        return value
