from django import forms

from reviews.models import REVIEW_TAGS


class ReviewForm(forms.Form):  # Mendefinisikan input dan validasi form tambah/edit ulasan.
    # Ownership and product IDs are always supplied by the server, never the form.
    rating = forms.TypedChoiceField(
        choices=[(value, f'{value} stars') for value in range(1, 6)], coerce=int,
        widget=forms.RadioSelect,
    )
    comment = forms.CharField(max_length=500, required=False, widget=forms.Textarea(attrs={
        'rows': 3, 'maxlength': 500, 'placeholder': 'Share a few words about this item...',
    }))
    tags = forms.MultipleChoiceField(
        choices=[(tag, tag) for tag in REVIEW_TAGS], required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('rating') in (1, 2) and not cleaned_data.get('comment'):
            self.add_error('comment', 'Tuliskan alasan kamu memberikan rating 1 atau 2.')
        return cleaned_data


class ReviewFilterForm(forms.Form):  # Memvalidasi parameter GET untuk menyaring daftar ulasan.
    scope = forms.ChoiceField(choices=[('written', 'Written by me'), ('received', 'Received as seller')], required=False)
    rating = forms.ChoiceField(choices=[('', 'All ratings')] + [(str(i), f'{i} stars') for i in range(1, 6)], required=False)
    q = forms.CharField(max_length=100, required=False, label='Product or comment')
    sort = forms.ChoiceField(choices=[('newest', 'Newest first'), ('oldest', 'Oldest first'), ('highest', 'Highest rating')], required=False)
