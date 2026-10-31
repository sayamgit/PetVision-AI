def showcase(request):
    return {'showcase_mode': request.user.is_authenticated and request.user.groups.filter(name='PetVision showcase').exists()}
