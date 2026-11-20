from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, get_object_or_404
from rest_framework.permissions import SAFE_METHODS, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from listings.models import Listing
from listings.serializers import ListingSerializer
from listings.services import EDIT_BLOCKED_BY_BIDS, ListingDeletionBlocked, delete_listing, has_active_bids


class ListingConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = 'listing_conflict'


class ListingPermission(IsAuthenticatedOrReadOnly):
    def has_object_permission(self, request, view, listing):
        if request.method not in SAFE_METHODS and listing.seller_id != request.user.pk:
            raise NotFound()
        return True


@method_decorator(never_cache, name='dispatch')
class ListingListAPI(ListCreateAPIView):
    queryset = Listing.objects.select_related('seller')
    serializer_class = ListingSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)


@method_decorator(never_cache, name='dispatch')
class ListingDetailAPI(RetrieveUpdateDestroyAPIView):
    queryset = Listing.objects.select_related('seller')
    serializer_class = ListingSerializer
    permission_classes = [ListingPermission]

    def get_locked_listing(self):
        queryset = self.get_queryset().filter(seller=self.request.user).select_for_update(of=('self',))
        listing = get_object_or_404(queryset, pk=self.kwargs['pk'])
        self.check_object_permissions(self.request, listing)
        return listing

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        listing = self.get_locked_listing()
        if has_active_bids(listing):
            raise ListingConflict(EDIT_BLOCKED_BY_BIDS)

        serializer = self.get_serializer(listing, data=request.data, partial=kwargs.get('partial', False))
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        listing = self.get_locked_listing()
        try:
            delete_listing(listing)
        except ListingDeletionBlocked as error:
            raise ListingConflict(str(error)) from error
        return Response(status=status.HTTP_204_NO_CONTENT)
