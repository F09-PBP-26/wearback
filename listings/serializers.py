from rest_framework import serializers

from listings.models import Listing, validate_https_url


class ListingSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source='seller.get_full_name', read_only=True)

    class Meta:
        model = Listing
        fields = [
            'id', 'seller', 'seller_name', 'name', 'description', 'price', 'image_url',
            'category', 'size', 'condition', 'brand', 'material', 'style', 'location',
            'stock', 'is_available', 'contact_email', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'seller', 'created_at', 'updated_at']
        extra_kwargs = {'image_url': {'validators': [validate_https_url]}}

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            fields.pop('contact_email')
        return fields

    def get_extra_kwargs(self):
        extra_kwargs = super().get_extra_kwargs()
        if self.instance is None:
            for name in Listing.REQUIRED_ON_CREATE:
                options = {'allow_null': False} if name == 'price' else {'allow_blank': False}
                extra_kwargs[name] = {'required': True, **options}
        return extra_kwargs
