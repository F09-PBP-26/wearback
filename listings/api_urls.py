from django.urls import path

from listings.api_views import ListingDetailAPI, ListingListAPI

app_name = 'listings_api'
urlpatterns = [
    path('', ListingListAPI.as_view(), name='list'),
    path('<int:pk>/', ListingDetailAPI.as_view(), name='detail'),
]
