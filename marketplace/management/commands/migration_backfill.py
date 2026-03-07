from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Backfill command retired after CP5 cleanup"

    def add_arguments(self, parser):
        parser.add_argument("--scope", default="all")

    def handle(self, *args, **options):
        raise CommandError("migration_backfill is retired after CP5 cleanup")
