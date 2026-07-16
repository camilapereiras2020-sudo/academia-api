from django.urls import path

from .views import WhatsAppReplyView

urlpatterns = [
    path("generar/", WhatsAppReplyView.as_view(), name="whatsapp-reply"),
]
