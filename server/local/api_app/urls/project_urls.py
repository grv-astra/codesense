# projects/urls.py
from django.urls import path
from ..views.project_views import ProjectListCreateView, ProjectListView, ProjectDetailView

urlpatterns = [
    path('', ProjectListCreateView.as_view()),
    path('names/', ProjectListView.as_view()),
    path('create/', ProjectListCreateView.as_view()),
    path('delete/<str:project_id>/', ProjectDetailView.as_view()),
    path('<str:project_id>/', ProjectDetailView.as_view()),
]
