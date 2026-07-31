from django.urls import path

from . import views

app_name = "terrain"

urlpatterns = [
    path("", views.config, name="config"),
    path("scan/", views.scan, name="scan"),
]
