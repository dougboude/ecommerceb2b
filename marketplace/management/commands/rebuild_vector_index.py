from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Rebuild the ChromaDB vector index from all listings"

    def handle(self, *args, **options):
        from marketplace.vector_search import rebuild_index

        self.stdout.write("Rebuilding vector index...")
        count = rebuild_index()
        self.stdout.write(self.style.SUCCESS(f"Indexed {count} listings."))
