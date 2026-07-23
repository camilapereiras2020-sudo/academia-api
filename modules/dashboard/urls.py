from django.urls import path

from .views import ReceptionSummaryView

urlpatterns = [
    path("reception-summary/", ReceptionSummaryView.as_view(), name="reception-summary"),
]
