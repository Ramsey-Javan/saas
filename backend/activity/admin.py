from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'activity_type',
        'title',
        'actor',
        'tenant',
        'is_system',
    )
    list_filter = ('activity_type', 'tenant', 'is_system', 'created_at')
    search_fields = ('title', 'description', 'target_name', 'actor__email')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'