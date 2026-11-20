from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

from main import views
from main.review_views import review_preview
from reviews.views import transaction_review

app_name = 'main'
router = DefaultRouter()
router.register(r"auctions", api_views.AuctionViewSet, basename="auction")

urlpatterns = [
    path('', views.show_main, name='show_main'),
    path('auction/', views.auction, name='auction'),
    path('auction/<int:listing_id>/bid/', views.place_bid, name='place_bid'),
    path('auction/<int:listing_id>/bid/<int:bid_id>/decision/', views.decide_bid, name='decide_bid'),
    path('reviews/preview/', review_preview, name='review_preview'),
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout, name='logout'),
    path('profile/', views.profile, name='profile'),

    # Transaction
    path("transactions/", views.transaction_history, name="transaction_history"),
    path('transactions/<int:transaction_id>/review/', transaction_review, name='transaction_review'),
    path('dropoff/<int:transaction_id>/', views.dropoff_locations, name='dropoff'),
    path('transactions/<int:transaction_id>/pay/', views.pay_transaction, name='pay_transaction'),

    # Cart
    path("cart/", views.cart, name="cart"),
    path("cart/<int:item_id>/remove/", views.remove_cart_item, name="remove_cart_item"),
    path("cart/checkout/", views.checkout_cart, name="checkout_cart"),
    path("cart/add/<int:listing_id>/", views.add_to_cart, name="add_to_cart"),

    path('sso/login/', views.sso_login, name='sso_login'),
    path('sso/callback/', views.sso_callback, name='sso_callback'),
    path('sso/link/', views.sso_link, name='sso_link'),
    
    path("api/", include(router.urls)),
    path("api/auth/login/", api_views.api_login, name="api_login"),
    path("api/auth/register/", api_views.api_register, name="api_register"),
    path("api/auth/logout/", api_views.api_logout, name="api_logout"),
    path("api/auth/profile/", api_views.api_profile, name="api_profile"),
]
