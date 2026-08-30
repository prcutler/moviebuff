import datetime

from django import forms
from django.utils import timezone

from .models import Watched, CustomWatchlist


class WatchedForm(forms.ModelForm):
    # Bootstrap classes are set on the widgets here rather than in the
    # template: Django's engine has no filter that takes widget attributes,
    # and the project installs no library that adds one.
    watched_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    watched_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        required=False,
    )
    # Backed by the model field now, so ticking it is recorded rather than
    # only bumping the counter on an entry that already existed.
    rewatch = forms.BooleanField(
        required=False,
        label="Re-watch",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = Watched
        fields = ['watched_date', 'watched_time', 'rating', 'review', 'rewatch']
        widgets = {
            'rating': forms.NumberInput(
                attrs={'step': 0.5, 'min': 0, 'max': 5, 'class': 'form-control'}
            ),
            'review': forms.Textarea(
                attrs={'maxlength': 300, 'class': 'form-control'}
            ),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        date = self.cleaned_data['watched_date']
        time_val = self.cleaned_data.get('watched_time') or datetime.time(0, 0)
        combined = datetime.datetime.combine(date, time_val)
        instance.watched_date = timezone.make_aware(combined)
        if commit:
            instance.save()
        return instance


class WatchlistForm(forms.Form):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        choices = [('default', 'Default Watchlist')]
        if user:
            custom_watchlists = CustomWatchlist.objects.filter(users=user)
            if custom_watchlists.exists():
                choices.extend(
                    [(watchlist.id, watchlist.name) for watchlist in custom_watchlists]
                )

        choices.append(('new', 'New Custom Watchlist'))

        self.fields['watchlist'] = forms.ChoiceField(
            choices=choices, label="Select Watchlist"
        )
        self.fields['new_watchlist_name'] = forms.CharField(
            max_length=255,
            required=False,
            label="New Watchlist Name",
            widget=forms.TextInput(attrs={'placeholder': 'Enter new watchlist name'}),
        )
        self.fields['new_watchlist_description'] = forms.CharField(
            widget=forms.Textarea(
                attrs={'placeholder': 'Enter new watchlist description'}
            ),
            required=False,
            label="New Watchlist Description",
        )

    def clean(self):
        cleaned_data = super().clean()
        watchlist_choice = cleaned_data.get('watchlist')

        if watchlist_choice == 'new':
            new_watchlist_name = cleaned_data.get('new_watchlist_name')
            if not new_watchlist_name:
                raise forms.ValidationError("New watchlist name is required.")

        return cleaned_data

