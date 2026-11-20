from rest_framework import serializers

from reviews.models import Review


class ReviewSerializer(serializers.ModelSerializer):
    """Data ulasan untuk Flutter; tidak mengekspos email pembeli."""

    product_name = serializers.CharField(source='transaction.item_name', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'transaction', 'listing', 'product_name', 'rating',
                  'comment', 'tags', 'created_at', 'updated_at']
        read_only_fields = fields
