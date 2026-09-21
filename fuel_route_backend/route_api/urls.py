from django.urls import path
from .views import RoutePreviewView, StartTripView, RefuelView, TripStatusView, FinishTripView

urlpatterns = [
    path("routes/preview/", RoutePreviewView.as_view(), name="route-preview"),
    path("trips/", StartTripView.as_view()),
    path("trips/<uuid:trip_id>/refuel/",RefuelView.as_view()),
    path("trips/<uuid:trip_id>/",TripStatusView.as_view()),
    path("trips/<uuid:trip_id>/finish/", FinishTripView.as_view()),
]