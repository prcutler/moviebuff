from django.apps import AppConfig


class ActivitypubConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'activitypub'

    def ready(self):
        import activitypub.signals
