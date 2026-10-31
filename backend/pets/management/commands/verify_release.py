import hashlib
import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from pets.image_engine import VERSION, CLASSES

class Command(BaseCommand):
    help = 'Verify deployable disease artifacts without printing secrets or changing weights.'
    def handle(self, *args, **options):
        for species, labels in CLASSES.items():
            folder=Path(settings.BASE_DIR).parent/'ml/artifacts'/VERSION/species
            try:
                metadata=json.loads((folder/'model_metadata.json').read_text())
                metrics=json.loads((folder/'test_metrics.json').read_text())
                with (folder/'best_model.pt').open('rb') as stream:
                    digest=hashlib.file_digest(stream,'sha256').hexdigest()
                if digest != metrics['model_sha256'] or metadata['classes'] != labels or metadata['species'] != species:
                    raise ValueError('Identity mismatch')
            except (OSError,ValueError,KeyError) as error:
                raise CommandError(f'{species} model is missing or does not match its tested export.') from error
            self.stdout.write(f'{species}: {VERSION} artifact verified')
