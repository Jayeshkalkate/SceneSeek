from django.urls import path
from core import views

urlpatterns = [
    path("", views.root, name="root"),
    path("ping", views.ping, name="ping"),
    path("healthz", views.health, name="health"),
    path("v1/config", views.public_config, name="public-config"),
    path("v1/auth/google", views.auth_google, name="auth-google"),
    path("v1/me", views.me, name="me"),
    path("v1/me/history", views.my_history, name="my-history"),
    path("v1/identify", views.identify, name="identify"),
    path("v1/jobs/<str:job_id>", views.get_job, name="job-status"),
    path("v1/feedback", views.submit_feedback, name="feedback"),
    path("v1/titles/<str:title_id>", views.title_detail, name="title-detail"),
    path("v1/stats/accuracy", views.accuracy_stats, name="accuracy-stats"),
    path("v1/takedown", views.submit_takedown, name="takedown"),
    path("v1/search", views.search, name="search"),
    path("v1/reference/status", views.reference_status, name="reference-status"),
]
