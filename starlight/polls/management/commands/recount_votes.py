from django.core.management.base import BaseCommand
from django.db.models import Count

from polls.models import Choice, Vote


class Command(BaseCommand):
    help = "Recompute Choice.votes from Vote rows (repairs lost counter increments)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report without writing.")

    def handle(self, *args, **options):
        actual = dict(
            Vote.objects.values_list("choice_id").annotate(n=Count("id")).order_by()
        )
        changed = 0
        for choice in Choice.objects.all():
            expected = actual.get(choice.pk, 0)
            if choice.votes != expected:
                changed += 1
                if not options["dry_run"]:
                    Choice.objects.filter(pk=choice.pk).update(votes=expected)
        if options["dry_run"]:
            self.stdout.write(f"{changed} would change")
        else:
            self.stdout.write(f"Updated {changed} choice(s)")
