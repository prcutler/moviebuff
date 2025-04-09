from django import forms
from .models import Watched, CustomWatchlist

class WatchedForm(forms.ModelForm):
    class Meta:
        model = Watched
        fields = ['watched_date', 'rating', 'review']
        widgets = {
            'watched_date': forms.DateInput(attrs={'type': 'date'}),
            'rating': forms.NumberInput(attrs={'step': 0.5, 'min': 0, 'max': 5}),
            'review': forms.Textarea(attrs={'maxlength': 300}),
        }

class WatchlistForm(forms.Form):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(WatchlistForm, self).__init__(*args, **kwargs)

        # Add the default watchlist option
        choices = [('default', 'Default Watchlist')]

        # Add existing custom watchlists if any
        if user:
            custom_watchlists = CustomWatchlist.objects.filter(users=user)
            if custom_watchlists.exists():
                choices.extend([(watchlist.id, watchlist.name) for watchlist in custom_watchlists])

        # Add the option to create a new custom watchlist
        choices.append(('new', 'New Custom Watchlist'))

        self.fields['watchlist'] = forms.ChoiceField(choices=choices, label="Select Watchlist")
        self.fields['new_watchlist_name'] = forms.CharField(max_length=255, required=False, label="New Watchlist Name", widget=forms.TextInput(attrs={'placeholder': 'Enter new watchlist name'}))
        self.fields['new_watchlist_description'] = forms.CharField(widget=forms.Textarea(attrs={'placeholder': 'Enter new watchlist description'}), required=False, label="New Watchlist Description")

    def clean(self):
        cleaned_data = super().clean()
        watchlist_choice = cleaned_data.get('watchlist')

        if watchlist_choice == 'new':
            new_watchlist_name = cleaned_data.get('new_watchlist_name')
            if not new_watchlist_name:
                raise forms.ValidationError("New watchlist name is required.")

        return cleaned_data