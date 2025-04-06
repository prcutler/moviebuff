from django import forms
from .models import Watched

class WatchedForm(forms.ModelForm):
    class Meta:
        model = Watched
        fields = ['watched_date', 'rating', 'review']
        widgets = {
            'watched_date': forms.DateInput(attrs={'type': 'date'}),
            'rating': forms.NumberInput(attrs={'step': 0.5, 'min': 0, 'max': 5}),
            'review': forms.Textarea(attrs={'maxlength': 300}),
        }
