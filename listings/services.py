from django.db import transaction
from django.db.models.deletion import ProtectedError

from main.models import Bid


EDIT_BLOCKED_BY_BIDS = 'This listing cannot be changed after bidding has started.'
DELETE_BLOCKED_BY_BIDS = 'This listing cannot be deleted after bidding has started.'
DELETE_BLOCKED_BY_REVIEWS = (
    'This listing has buyer reviews and cannot be deleted. Set its stock to 0 to stop selling it.'
)
DELETE_BLOCKED_BY_ORDERS = 'This listing has paid orders awaiting seller confirmation and cannot be deleted.'
DELETE_BLOCKED_BY_PROTECTED_RECORDS = (
    'This listing is linked to protected records and cannot be deleted. Set its stock to 0 to stop selling it.'
)


class ListingDeletionBlocked(Exception):
    def __init__(self, message, *, has_paid_orders=False):
        super().__init__(message)
        self.has_paid_orders = has_paid_orders


def has_active_bids(listing):
    return listing.bids.filter(status__in=[Bid.Status.PENDING, Bid.Status.APPROVED]).exists()


def delete_listing(listing):
    """Delete a listing after the caller has locked its row."""
    if has_active_bids(listing):
        raise ListingDeletionBlocked(DELETE_BLOCKED_BY_BIDS)
    if listing.reviews.exists():
        raise ListingDeletionBlocked(DELETE_BLOCKED_BY_REVIEWS)
    if listing.transactions.filter(status='paid').exists():
        raise ListingDeletionBlocked(DELETE_BLOCKED_BY_ORDERS, has_paid_orders=True)

    try:
        with transaction.atomic():
            listing.delete()
    except ProtectedError as error:
        raise ListingDeletionBlocked(DELETE_BLOCKED_BY_PROTECTED_RECORDS) from error
