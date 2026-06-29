from django.apps import AppConfig
from django.db.models.signals import post_migrate


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"
    verbose_name = "Event Management"

    def ready(self):
        from .seed import seed_database
        post_migrate.connect(seed_database, sender=self, dispatch_uid="events.seed_database")

