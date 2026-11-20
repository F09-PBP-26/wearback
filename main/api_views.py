from django.contrib.auth import authenticate, login, logout, get_user_model
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from listings.models import Listing
from .models import Bid
from .serializers import (
    UserProfileSerializer,
    RegisterSerializer,
    AuctionListingSerializer,
    BidSerializer,
)

User = get_user_model()


# --- 1. ENDPOINT AUTENTIKASI & PROFIL ---

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


# --- 2. ENDPOINT AUCTION (BERBASIS LISTING & BID) ---

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