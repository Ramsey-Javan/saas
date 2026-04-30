from django.urls import path
from .views import SchoolBrandingView

app_name = 'branding'

urlpatterns = [
    path('', SchoolBrandingView.as_view(), name='school-branding'),
]
