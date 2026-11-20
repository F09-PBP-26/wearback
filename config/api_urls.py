"""URL configuration for the version 1 REST API."""

from django.urls import include, path

app_name = 'api_v1'
urlpatterns = [
    path('listings/', include('listings.api_urls')),
]
