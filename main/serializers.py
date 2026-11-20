from rest_framework import serializers
from main.models import CartItem, TransactionHistory

# Transactions
class TransactionHistorySerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = TransactionHistory
        fields = [
            "id", "order_number", 
            "item_name", "item_image_url", "item_summary",
            "price", "item_count",
            "seller_name",
            "status", "status_display", "status_message",
            "payment_deadline", "created_at", "updated_at", "completed_at",
        ]
        read_only_fields = fields

# Carts
class CartItemSerializer(serializers.ModelSerializer):
    listing_id = serializers.IntegerField(read_only=True)
    listing_name = serializers.CharField(
        source="listing.name",
        read_only=True
    )
    listing_price = serializers.DecimalField(
        source="listing.price",
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    listing_image = serializers.URLField(
        source="listing.image_url",
        read_only=True
    )
    listing_stock = serializers.IntegerField(
        source="listing.stock",
        read_only=True
    )

    class Meta:
        model = CartItem
        fields = [
            "id", "listing_id",
            "listing_name", "listing_price", "listing_image", "listing_stock",
            "quantity", "selected", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

class CheckoutSerializer(serializers.Serializer):
    cart_item_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )