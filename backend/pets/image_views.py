from io import BytesIO
import uuid
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction, IntegrityError
from django.http import FileResponse,Http404,HttpResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.http import require_POST
from .models import PhotoCheck, Conversation
from .care_ui import vet_contact
from .image_forms import PhotoCheckForm
from .image_engine import predict,ModelUnavailable,CLASSES
from .views import owned_pet,limited,too_many

@login_required
def start(request,pk=None):
    pet = owned_pet(request,pk) if pk is not None else None
    form = PhotoCheckForm(request.POST or None,request.FILES or None,initial={'request_id':uuid.uuid4()},user=request.user,pet=pet)
    if request.method == 'POST':
        if limited(request,'photo-check',12):
            return too_many()
        if form.is_valid():
            selected_pet = form.cleaned_data.get('pet')
            species = form.cleaned_data['species']
            key = form.cleaned_data['request_id']
            old = PhotoCheck.objects.filter(pk=key).first()
            if old:
                if old.owner_id!=request.user.pk:
                    return HttpResponse('Invalid request identifier.',status=400)
                return redirect('photo_result',key=old.pk)
            image = form.cleaned_data['image']
            try:
                try:
                    if form.cleaned_data['purpose'] == 'general':
                        result = {'purpose':'general','version':'general-check-v1','status':'not_assessed','ranked':[]}
                    else:
                        result = {**predict(image,species), 'purpose':'concern'}
                except ModelUnavailable as error:
                    form.add_error(None,str(error))
                else:
                    preview = image.copy()
                    try:
                        preview.thumbnail((1200,1200))
                        output = BytesIO()
                        preview.save(output,'JPEG',quality=88)
                    finally:
                        preview.close()
                    record = PhotoCheck(id=key,owner=request.user,pet=selected_pet,species=species,result=result,observations=form.cleaned_data['observations'])
                    record.image.save('photo.jpg',ContentFile(output.getvalue()),save=False)
                    try:
                        with transaction.atomic():
                            record.save(force_insert=True)
                    except IntegrityError:
                        record.image.delete(save=False)
                        existing=get_object_or_404(PhotoCheck,pk=key,owner=request.user)
                        return redirect('photo_result',key=existing.pk)
                    except Exception:
                        record.image.delete(save=False)
                        raise
                    return redirect('photo_result',key=record.pk)
            finally:
                image.close()
    return render(request,'images/start.html',{'pet':pet,'form':form,'checks':(pet.photo_checks.all() if pet else PhotoCheck.objects.filter(owner=request.user))[:20],'classes':CLASSES[pet.species] if pet else [],'general':pet is None})

@login_required
def result(request,key):
    record=get_object_or_404(PhotoCheck.objects.select_related('pet'),pk=key,owner=request.user)
    if record.is_general_check:
        if request.GET.get('focus'):
            return HttpResponse('A general check has no disease matches.', status=400)
        return render(request,'images/general_result.html',{'check':record,'pet':record.pet})
    from .photo_followup import result_context
    context = result_context(request, record)
    if context is None:
        return HttpResponse('Invalid prediction selection.', status=400)
    return render(request,'images/result.html',{**context,'vet_contact':vet_contact(record.pet, request.user),'care_pet':record.pet,'check':record,'pet':record.pet,'top':record.result['ranked'][0],'ranked':record.result['ranked'][1:],'ring_offset':100-record.result['ranked'][0]['score'],'remaining_score':sum(item['score'] for item in record.result['ranked'][1:])})

@login_required
def photo(request,key):
    record=get_object_or_404(PhotoCheck,pk=key,owner=request.user)
    try:
        return FileResponse(record.image.open('rb'),content_type='image/jpeg')
    except FileNotFoundError:
        raise Http404

@login_required
@require_POST
def delete(request,key):
    record=get_object_or_404(PhotoCheck,pk=key,owner=request.user)
    if request.POST.get('confirm')!='yes':
        return HttpResponse('Confirm deletion.',status=400)
    pet_id=record.pet_id
    storage,name=record.image.storage,record.image.name
    with transaction.atomic():
        record.delete()
        transaction.on_commit(lambda:storage.delete(name))
    return redirect('photo_start',pk=pet_id) if pet_id else redirect('photo_general')
