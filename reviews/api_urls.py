from django.urls import path

from reviews.api_views import ReviewDetailAPI, ReviewListAPI

app_name = 'reviews_api'
urlpatterns = [
    path('', ReviewListAPI.as_view(), name='list'),
    path('<int:pk>/', ReviewDetailAPI.as_view(), name='detail'),
]
