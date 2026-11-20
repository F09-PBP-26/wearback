from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from listings.models import Listing
from main.models import TransactionHistory
from reviews.models import Review


class ReviewAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.buyer = user.objects.create_user(username='api-buyer')
        cls.other = user.objects.create_user(username='api-other')
        listing = Listing.objects.create(seller=cls.other, name='Jacket', price=100000)
        order = TransactionHistory.objects.create(
            buyer=cls.buyer, listing=listing, item_name='Jacket',
            price=100000, status='completed',
        )
        cls.review = Review.objects.create(
            transaction=order, listing=listing, reviewer=cls.buyer,
            rating=5, comment='Great', tags=['Quality'],
        )

    def test_anonymous_access_is_denied(self):
        for url in [reverse('reviews_api:list'),
                    reverse('reviews_api:detail', args=[self.review.pk])]:
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_owner_can_read_paginated_json_and_detail(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse('reviews_api:list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)
        item = response.json()['results'][0]
        self.assertEqual(item['product_name'], 'Jacket')
        self.assertEqual(item['tags'], ['Quality'])
        self.assertNotIn('reviewer', item)
        self.assertContains(response, 'Great')
        self.assertIn('no-store', response['Cache-Control'])
        response = self.client.get(reverse('reviews_api:detail', args=[self.review.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], self.review.pk)

    def test_other_user_cannot_read_review(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('reviews_api:list')).json()['count'], 0)
        response = self.client.get(reverse('reviews_api:detail', args=[self.review.pk]))
        self.assertEqual(response.status_code, 404)

    def test_endpoint_is_read_only(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.post(reverse('reviews_api:list'), {}).status_code, 405)
