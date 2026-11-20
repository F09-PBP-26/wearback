from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from reviews.models import Review
from reviews.serializers import ReviewSerializer


class ReviewPagination(PageNumberPagination):
    page_size = 10


class OwnReviewQueryset:
    serializer_class = ReviewSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Identitas diambil dari sesi login, bukan parameter dari pengguna.
        return Review.objects.filter(reviewer=self.request.user).select_related(
            'transaction',
        ).order_by('-created_at', '-pk')


@method_decorator(never_cache, name='dispatch')
class ReviewListAPI(OwnReviewQueryset, ListAPIView):
    pagination_class = ReviewPagination


@method_decorator(never_cache, name='dispatch')
class ReviewDetailAPI(OwnReviewQueryset, RetrieveAPIView):
    pass
