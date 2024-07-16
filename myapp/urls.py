# myapp/urls.py
from django.urls import path
from . import views
urlpatterns = [
    path('', views.index, name='index'),
    path('recommendate/', views.recommendate, name='recommendate'),
]