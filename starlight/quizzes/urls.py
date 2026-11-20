from django.urls import path

from . import views

app_name = "quizzes"
urlpatterns = [
    path("", views.TopicListView.as_view(), name="index"),
    path("topics/<slug:slug>/", views.TopicDetailView.as_view(), name="topic"),
    path("quiz/<slug:slug>/", views.QuizDetailView.as_view(), name="detail"),
    path("quiz/<slug:slug>/take/", views.take, name="take"),
    path("attempts/", views.AttemptListView.as_view(), name="attempts"),
    path("attempts/<int:pk>/", views.AttemptDetailView.as_view(), name="attempt"),
]
