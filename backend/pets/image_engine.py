"""CPU inference for the verified curated-v2 exports; no runtime downloads."""
from functools import lru_cache
import hashlib
import json
import threading
from pathlib import Path
from django.conf import settings
from PIL import Image, ImageOps

VERSION = 'curated-v2'
PREPROCESS = {'size':224,'mode':'fit_inside_square_then_pad','padding_rgb':[128,128,128],
              'mean':[0.485,0.456,0.406],'std':[0.229,0.224,0.225]}
CLASSES = {'cat':['Dental Disease','Ear Mites','Eye Infection','Fungal skin condition','Normal-looking skin','Scabies'],
           'dog':['Dental Disease','Eye Infection','Fungal skin condition','Hot Spots','Mange','Normal-looking skin','Tick Infestation']}
LOCK = threading.Lock()

class ModelUnavailable(Exception):
    pass

def square_image(image):
    # Validated uploads are already oriented RGB. Avoid two full-size copies;
    # retain the exact original resize, padding and orientation behavior.
    if image.mode == 'RGB' and image.getexif().get(274, 1) == 1:
        fitted = ImageOps.contain(image, (224, 224), method=Image.Resampling.BILINEAR)
    else:
        with ImageOps.exif_transpose(image) as oriented:
            with oriented.convert('RGB') as rgb:
                fitted = ImageOps.contain(rgb, (224, 224), method=Image.Resampling.BILINEAR)
    with fitted:
        canvas = Image.new('RGB', (224, 224), (128, 128, 128))
        canvas.paste(fitted, ((224-fitted.width)//2, (224-fitted.height)//2))
    return canvas

@lru_cache(maxsize=2)
def load_model(species):
    if species not in CLASSES:
        raise ModelUnavailable('Choose a cat or dog profile.')
    try:
        import torch
        from torchvision import models
        folder = Path(settings.BASE_DIR).parent/'ml'/'artifacts'/VERSION/species
        metadata = json.loads((folder/'model_metadata.json').read_text())
        metrics = json.loads((folder/'test_metrics.json').read_text())
        path = folder/'best_model.pt'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != metrics['model_sha256']:
            raise ValueError('Model checksum differs from tested export')
        if (metadata['species'] != species or metadata['classes'] != CLASSES[species]
                or metadata['config']['architecture'] != 'mobilenet_v3_small'
                or metadata['config']['preprocess'] != PREPROCESS):
            raise ValueError('Unexpected metadata')
        export = torch.load(path,map_location='cpu',weights_only=True)
        if export['identity'] != metadata:
            raise ValueError('Export identity differs from metadata')
        torch.set_num_threads(2)
        model = models.mobilenet_v3_small(weights=None)
        model.classifier[-1] = torch.nn.Linear(model.classifier[-1].in_features,len(CLASSES[species]))
        model.load_state_dict(export['model_state'],strict=True)
        model.eval()
        return model,metrics,digest
    except (ImportError,OSError,ValueError,KeyError,RuntimeError,TypeError) as error:
        raise ModelUnavailable('Photo analysis is temporarily unavailable. Please try again later.') from error

def predict(image,species):
    try:
        import torch
        from torchvision.transforms import functional as F
        with LOCK:
            model,metrics,digest = load_model(species)
            tensor = F.normalize(F.to_tensor(square_image(image)),PREPROCESS['mean'],PREPROCESS['std']).unsqueeze(0)
            with torch.inference_mode():
                scores = model(tensor).softmax(dim=1)[0]
            if not torch.isfinite(scores).all():
                raise ValueError('Invalid scores')
            ranked = sorted([{'label':label,'score':float(score)*100} for label,score in zip(CLASSES[species],scores)],key=lambda row:row['score'],reverse=True)
        return {'version':VERSION,'species':species,'model_sha256':digest,'ranked':ranked,
                'test_accuracy':metrics['all_files']['accuracy']*100,'test_count':metrics['all_files']['count'],
                'test_macro_f1':metrics['all_files']['macro_f1']}
    except (ImportError,RuntimeError,ValueError) as error:
        raise ModelUnavailable('Photo analysis is temporarily unavailable. Please try again later.') from error
