from django.urls import path
from .views import dashboard_stats, upcoming_events, SchoolEventViewSet

school_event_list = SchoolEventViewSet.as_view({'get': 'list', 'post': 'create'})
school_event_detail = SchoolEventViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'})

urlpatterns = [
    path('stats/', dashboard_stats, name='dashboard-stats'),
    path('upcoming-events/', upcoming_events, name='dashboard-upcoming-events'),
    path('events/', school_event_list, name='school-event-list'),
    path('events/<int:pk>/', school_event_detail, name='school-event-detail'),
]