from django.core.management.base import BaseCommand

from fedi.models import FediDelivery
from fedi.tasks import deliver_activity


class Command(BaseCommand):
    help = "Process queued ActivityPub deliveries"

    def add_arguments(self, parser):
        parser.add_argument(
            "--retry-failed",
            action="store_true",
            help="Also retry deliveries that previously failed",
        )

    def handle(self, *args, **options):
        statuses = [FediDelivery.QUEUED]
        if options["retry_failed"]:
            statuses.append(FediDelivery.FAILED)

        deliveries = FediDelivery.objects.filter(status__in=statuses).values_list(
            "activity_id", "follower_id"
        )
        total = deliveries.count()

        if total == 0:
            self.stdout.write("No pending deliveries.")
            return

        self.stdout.write(f"Processing {total} deliveries...")
        sent = 0
        failed = 0

        for activity_id, follower_id in deliveries:
            deliver_activity(activity_id, follower_id)
            delivery = FediDelivery.objects.get(activity_id=activity_id, follower_id=follower_id)
            if delivery.status == FediDelivery.SENT:
                sent += 1
            else:
                failed += 1

        self.stdout.write(f"Done: {sent} sent, {failed} failed.")
