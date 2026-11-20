from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from listings.models import Listing
from main.models import Bid, TransactionHistory
from reviews.models import Review


class ListingAPITests(TestCase):
    creation_data = {
        'name': 'Vintage coat', 'price': '150000.50', 'category': 'outerwear',
        'size': 'Medium', 'condition': 'good',
    }

    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.seller = user.objects.create_user(
            username='api-seller', email='private@example.com', first_name='Seller',
        )
        cls.buyer = user.objects.create_user(username='api-buyer')
        cls.listing = Listing.objects.create(
            seller=cls.seller, name='Legacy scarf', contact_email='published@example.com',
        )

    def setUp(self):
        self.client = APIClient()
        self.collection = reverse('api_v1:listings_api:list')
        self.detail = reverse('api_v1:listings_api:detail', args=[self.listing.pk])

    def test_public_list_is_paginated_and_newest_first(self):
        listings = Listing.objects.bulk_create([
            Listing(seller=self.seller, name=f'Item {index}', price=20000, stock=0)
            for index in range(20)
        ])
        response = self.client.get(self.collection)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 21)
        self.assertEqual([item['id'] for item in data['results']], [item.pk for item in reversed(listings)])
        self.assertFalse(data['results'][0]['is_available'])
        self.assertIn('page=2', data['next'])
        next_page = self.client.get(self.collection, {'page': 2}).json()
        self.assertEqual(next_page['results'][0]['id'], self.listing.pk)
        self.assertNotIn('contact_email', next_page['results'][0])

    def test_detail_hides_contact_from_guests_and_never_discloses_account_email(self):
        response = self.client.get(self.detail)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['seller_name'], 'Seller')
        self.assertIsNone(data['price'])
        self.assertFalse(data['is_available'])
        self.assertNotIn('contact_email', data)
        self.assertEqual(self.client.get(f'{self.collection}{self.listing.pk + 1}/').status_code, 404)

        self.client.force_login(self.buyer)
        for url in (self.collection, self.detail):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, self.listing.contact_email)
                self.assertNotContains(response, self.seller.email)
                self.assertIn('no-store', response['Cache-Control'])

    def test_create_assigns_seller_from_session_and_uses_model_defaults(self):
        self.client.force_login(self.seller)
        image_url = 'https://example.com/coat.png'
        response = self.client.post(
            self.collection, {**self.creation_data, 'seller': self.buyer.pk, 'image_url': image_url}, format='json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['seller'], self.seller.pk)
        self.assertEqual(data['price'], '150000.50')
        self.assertEqual(data['image_url'], image_url)
        self.assertEqual(data['stock'], 1)
        self.assertTrue(data['is_available'])
        self.assertTrue(Listing.objects.filter(pk=data['id'], seller=self.seller).exists())

    def test_create_validates_required_fields_and_model_constraints(self):
        self.client.force_login(self.seller)
        response = self.client.post(self.collection, {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()), set(self.creation_data))

        invalid_fields = [
            ('name', ' '), ('price', None), ('price', '0'), ('category', ' '),
            ('category', 'unknown'), ('size', ' '), ('condition', ''),
            ('image_url', 'http://example.com/item.png'), ('stock', -1), ('stock', 10000),
            ('contact_email', 'invalid'),
        ]
        for field, value in invalid_fields:
            with self.subTest(field=field, value=value):
                response = self.client.post(self.collection, {**self.creation_data, field: value}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        self.assertEqual(Listing.objects.count(), 1)

    def test_guests_and_other_members_cannot_write(self):
        self.assertEqual(self.client.post(self.collection, self.creation_data, format='json').status_code, 403)
        for method in (self.client.put, self.client.patch, self.client.delete):
            self.assertEqual(method(self.detail, self.creation_data, format='json').status_code, 403)

        self.client.force_login(self.buyer)
        for method in (self.client.put, self.client.patch, self.client.delete):
            self.assertEqual(method(self.detail, self.creation_data, format='json').status_code, 404)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.name, 'Legacy scarf')

    def test_options_only_shows_edit_fields_to_owner(self):
        self.client.force_login(self.buyer)
        self.assertNotIn('PUT', self.client.options(self.detail).json().get('actions', {}))
        self.client.force_login(self.seller)
        self.assertIn('PUT', self.client.options(self.detail).json()['actions'])

    def test_owner_can_patch_put_and_delete_legacy_listing(self):
        self.client.force_login(self.seller)
        response = self.client.patch(self.detail, {'stock': 0, 'seller': self.buyer.pk}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['stock'], 0)
        self.assertEqual(response.json()['name'], self.listing.name)
        self.assertEqual(response.json()['seller'], self.seller.pk)

        response = self.client.put(self.detail, {'name': 'Renamed scarf'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.name, 'Renamed scarf')
        self.assertEqual(self.listing.stock, 0)
        self.assertIsNone(self.listing.price)

        self.assertEqual(self.client.delete(self.detail).status_code, 204)
        self.assertEqual(self.client.get(self.detail).status_code, 404)

    def test_session_authenticated_writes_require_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.seller)
        client.get(reverse('main:show_main'))
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        denied = client.patch(self.detail, {'stock': 2}, format='json')
        self.assertEqual(denied.status_code, 403)
        self.assertIn('CSRF', denied.json()['detail'])
        allowed = client.patch(self.detail, {'stock': 2}, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(allowed.status_code, 200)

    def test_pending_and_approved_bids_block_edits_and_deletes(self):
        self.client.force_login(self.seller)
        bid = Bid.objects.create(listing=self.listing, bidder=self.buyer, amount=100000)
        for bid_status in (Bid.Status.PENDING, Bid.Status.APPROVED):
            with self.subTest(status=bid_status):
                Bid.objects.filter(pk=bid.pk).update(status=bid_status)
                response = self.client.patch(self.detail, {'name': 'Renamed scarf'}, format='json')
                self.assertEqual(response.status_code, 409)
                self.assertEqual(self.client.delete(self.detail).status_code, 409)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.name, 'Legacy scarf')

    def test_paid_orders_and_reviews_block_deletion(self):
        self.client.force_login(self.seller)
        order = TransactionHistory.objects.create(
            buyer=self.buyer, listing=self.listing, item_name=self.listing.name,
            price=100000, status='paid',
        )
        response = self.client.delete(self.detail)
        self.assertEqual(response.status_code, 409)
        self.assertIn('paid orders', response.json()['detail'])

        order.status = 'completed'
        order.save(update_fields=['status'])
        Review.objects.create(transaction=order, listing=self.listing, reviewer=self.buyer, rating=5)
        response = self.client.delete(self.detail)
        self.assertEqual(response.status_code, 409)
        self.assertIn('buyer reviews', response.json()['detail'])
        self.assertTrue(Listing.objects.filter(pk=self.listing.pk).exists())
