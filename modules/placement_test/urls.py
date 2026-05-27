
from django.urls import path
from . import views

urlpatterns = [
    path("placement/start/", views.start_session),
    path("placement/submit/<str:session_id>/", views.submit_answers),
    path("placement/contact/<int:result_id>/", views.save_contact),
    path("placement/results/", views.list_results),
]
