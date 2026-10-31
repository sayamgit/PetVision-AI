from django.urls import include, path
from pets.health import health
urlpatterns = [path('healthz/', health, name='health'), path('', include('pets.urls'))]
