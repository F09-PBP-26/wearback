from datetime import timedelta

from django.contrib.auth import authenticate, login, logout, get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    action,
)
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from listings.models import Listing
from main.models import Bid, CartItem, TransactionHistory
from main.serializers import (
    UserProfileSerializer,
    RegisterSerializer,
    AuctionListingSerializer,
    BidSerializer,
    CartItemSerializer,
    TransactionHistorySerializer,
    CheckoutSerializer,
)

User = get_user_model()


# --- 1. ENDPOINT AUTENTIKASI & PROFIL (UZA) ---

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def api_login(request):
    identifier = (request.data.get("email") or request.data.get("username") or "").strip()
    password = request.data.get("password", "")

    user = authenticate(request, username=identifier, password=password)
    if user is None and "@" in identifier:
        matched = User.objects.filter(email__iexact=identifier).first()
        if matched:
            user = authenticate(request, username=matched.username, password=password)

    if user is None:
        return Response(
            {"status": False, "message": "Email atau password salah."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    login(request, user)
    return Response({
        "status": True,
        "message": "Login berhasil.",
        "user": UserProfileSerializer(user).data,
    })


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def api_register(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response(
            {
                "status": True,
                "message": "Registrasi berhasil.",
                "user": UserProfileSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )
    return Response(
        {"status": False, "errors": serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_logout(request):
    logout(request)
    return Response({"status": True, "message": "Logout berhasil."})


@csrf_exempt
@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def api_profile(request):
    if request.method == "GET":
        return Response({"status": True, "user": UserProfileSerializer(request.user).data})

    serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({"status": True, "message": "Profil diperbarui.", "user": serializer.data})
    return Response({"status": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


# --- 2. ENDPOINT AUCTION (UZA) ---

class AuctionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    - GET /api/auctions/          -> Daftar listing yang dilelang
    - GET /api/auctions/<id>/     -> Detail lelang & riwayat penawaran
    - POST /api/auctions/<id>/bid/ -> Ajukan penawaran baru
    - GET /api/auctions/my-bids/  -> Riwayat penawaran user yang login
    """
    queryset = Listing.objects.all().order_by("-id")
    serializer_class = AuctionListingSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def bid(self, request, pk=None):
        listing = self.get_object()

        if getattr(listing, "seller_id", None) == request.user.id:
            return Response(
                {"status": False, "message": "Penjual tidak dapat menawar barang miliknya sendiri."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if listing.bids.filter(status=Bid.Status.PENDING).exists():
            return Response(
                {
                    "status": False,
                    "message": "Sudah ada penawaran pending yang menunggu persetujuan penjual.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BidSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"status": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        amount = serializer.validated_data["amount"]
        highest = listing.bids.filter(status=Bid.Status.APPROVED).order_by("-amount").first()
        min_required = highest.amount if highest else getattr(listing, "price", 0)

        if amount <= min_required:
            return Response(
                {"status": False, "message": f"Penawaran harus lebih tinggi dari Rp{min_required:,.0f}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            serializer.save(listing=listing, bidder=request.user)
        except IntegrityError:
            return Response(
                {"status": False, "message": "Penawaran lain sedang diproses untuk item ini."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "status": True,
                "message": "Penawaran berhasil diajukan dan menunggu persetujuan penjual.",
                "auction": AuctionListingSerializer(listing).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated], url_path="my-bids")
    def my_bids(self, request):
        bids = Bid.objects.filter(bidder=request.user).select_related("listing").order_by("-created_at")
        return Response({"status": True, "results": BidSerializer(bids, many=True).data})


# --- 3. ENDPOINT TRANSACTIONS & CARTS (FATHIR) ---

@api_view(["GET", "HEAD"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def transaction_history_list(request):
    now = timezone.now()

    TransactionHistory.objects.filter(
        buyer=request.user,
        status="ongoing",
        payment_deadline__isnull=False,
        payment_deadline__lte=now,
    ).update(
        status="cancelled",
        status_message="Payment time expired",
        updated_at=now,
    )

    transactions = TransactionHistory.objects.filter(buyer=request.user).order_by("-created_at")
    serializer = TransactionHistorySerializer(transactions, many=True, context={"request": request})

    return Response(serializer.data)


@api_view(["GET", "HEAD"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def cart_list(request):
    cart_items = CartItem.objects.filter(buyer=request.user).select_related("listing").order_by("-created_at")
    serializer = CartItemSerializer(cart_items, many=True)

    return Response(serializer.data)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def cart_add(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id)

    if listing.bids.filter(status__in=["pending", "approved"]).exists():
        return Response(
            {"error": "This item is available through auction only."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if listing.stock <= 0:
        return Response(
            {"error": "Item is out of stock."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        quantity = int(request.data.get("quantity", 1))
    except (TypeError, ValueError):
        return Response(
            {"error": "Invalid quantity."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if quantity < 1 or quantity > listing.stock:
        return Response(
            {"error": "Invalid quantity."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cart_item, created = CartItem.objects.get_or_create(
        buyer=request.user,
        listing=listing,
        defaults={"quantity": quantity, "selected": True},
    )

    if not created:
        new_quantity = cart_item.quantity + quantity

        if new_quantity > listing.stock:
            return Response(
                {"error": "Quantity exceeds available stock."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart_item.quantity = new_quantity
        cart_item.save(update_fields=["quantity"])

    serializer = CartItemSerializer(cart_item)

    return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(["DELETE"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def cart_delete(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, buyer=request.user)
    cart_item.delete()

    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def cart_checkout(request):
    input_serializer = CheckoutSerializer(data=request.data)
    input_serializer.is_valid(raise_exception=True)
    item_ids = list(set(input_serializer.validated_data["cart_item_ids"]))

    deadline = timezone.now() + timedelta(minutes=10)

    with transaction.atomic():
        cart_items = list(
            CartItem.objects
            .filter(buyer=request.user, id__in=item_ids, selected=True)
            .select_related("listing", "listing__seller")
            .select_for_update(of=("self",))
        )

        if not cart_items:
            return Response(
                {"error": "No selected cart items found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for item in cart_items:
            listing = item.listing

            if listing is None:
                return Response(
                    {"error": "A listing in your cart no longer exists."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if listing.bids.filter(status__in=[Bid.Status.PENDING, Bid.Status.APPROVED]).exists():
                return Response(
                    {"error": f"{listing.name} is in an auction and cannot be purchased through the cart."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if listing.price is None or listing.price <= 0:
                return Response(
                    {"error": f"{listing.name} has an invalid price."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if item.quantity < 1 or item.quantity > listing.stock:
                return Response(
                    {"error": f"Invalid quantity for {listing.name}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        created = []
        for item in cart_items:
            listing = item.listing
            created.append(TransactionHistory.objects.create(
                buyer=request.user,
                listing=listing,
                item_name=listing.name,
                item_image_url=listing.image_url or "",
                price=listing.price * item.quantity,
                status="ongoing",
                item_count=item.quantity,
                seller_name=listing.seller.get_full_name().strip(),
                payment_deadline=deadline,
            ))

        CartItem.objects.filter(
            buyer=request.user, id__in=[item.id for item in cart_items]
        ).delete()

    serializer = TransactionHistorySerializer(created, many=True)
    return Response(serializer.data, status=status.HTTP_201_CREATED)