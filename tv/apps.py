from django.apps import AppConfig


class TvConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tv'

    def ready(self):
        # Import signals for TV-related ActivityPub events
        from . import signals  # noqa: F401
