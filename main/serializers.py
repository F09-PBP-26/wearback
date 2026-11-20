import uuid
from django.contrib.auth import get_user_model
from rest_framework import serializers
from listings.models import Listing
from main.models import Bid, CartItem, TransactionHistory

User = get_user_model()


# --- 1. SERIALIZER AUTENTIKASI, PROFIL, & AUCTION (UZA) ---

class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "full_name", "location"]
        read_only_fields = ["id", "username"]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.email or obj.username


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ["email", "password", "first_name", "last_name", "location"]

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Email sudah terdaftar.")
        return email

    def create(self, validated_data):
        email = validated_data["email"]
        base_username = email.split("@")[0][:20]
        username = f"{base_username}_{uuid.uuid4().hex[:6]}"
        return User.objects.create_user(
            username=username,
            email=email,
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            location=validated_data.get("location", ""),
        )


class BidSerializer(serializers.ModelSerializer):
    bidder_name = serializers.SerializerMethodField()
    listing_name = serializers.CharField(source="listing.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Bid
        fields = [
            "id",
            "listing",
            "listing_name",
            "bidder_name",
            "amount",
            "amount_display",
            "status",
            "status_display",
            "created_at",
            "approved_at",
        ]
        read_only_fields = ["id", "listing", "status", "created_at", "approved_at"]

    def get_bidder_name(self, obj):
        return obj.bidder.get_full_name() or obj.bidder.email or obj.bidder.username


class AuctionListingSerializer(serializers.ModelSerializer):
    starting_price = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()
    has_pending_bid = serializers.SerializerMethodField()
    total_bids = serializers.SerializerMethodField()
    winner = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    seller_name = serializers.SerializerMethodField()
    bids = BidSerializer(many=True, read_only=True)

    class Meta:
        model = Listing
        fields = [
            "id",
            "name",
            "description",
            "category",
            "size",
            "condition",
            "image_url",
            "seller_name",
            "starting_price",
            "current_price",
            "has_pending_bid",
            "total_bids",
            "winner",
            "bids",
        ]

    def get_starting_price(self, obj):
        return float(getattr(obj, "price", 0))

    def get_current_price(self, obj):
        highest = obj.bids.exclude(status=Bid.Status.REJECTED).order_by("-amount", "created_at").first()
        return float(highest.amount if highest else getattr(obj, "price", 0))

    def get_has_pending_bid(self, obj):
        return obj.bids.filter(status=Bid.Status.PENDING).exists()

    def get_total_bids(self, obj):
        return obj.bids.count()

    def get_winner(self, obj):
        approved = obj.bids.filter(status=Bid.Status.APPROVED).order_by("-amount", "approved_at").first()
        if not approved:
            return None
        return approved.bidder.get_full_name() or approved.bidder.email or approved.bidder.username

    def get_image_url(self, obj):
        return getattr(obj, "image_url", "") or ""

    def get_seller_name(self, obj):
        seller = getattr(obj, "seller", None)
        if not seller:
            return ""
        return seller.get_full_name() or seller.email or seller.username


# --- 2. SERIALIZER TRANSACTIONS & CARTS (FATHIR) ---

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