from django.urls import path
from main import api_views

app_name = "api"

urlpatterns = [
    # Transactions
    path("transactions/history/", api_views.transaction_history_list, name="transaction-history"),

    # Carts
    path("cart/", api_views.cart_list, name="cart-list"),
    path("cart/add/<int:listing_id>/", api_views.cart_add, name="cart-add"),
    path("cart/checkout/", api_views.cart_checkout, name="cart-checkout"),
    path("cart/<int:item_id>/", api_views.cart_delete, name="cart-delete"),
]