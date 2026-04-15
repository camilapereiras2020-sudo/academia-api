files = {
    'modules/alumnos/urls.py': 'from rest_framework.routers import DefaultRouter\nfrom .views import AlumnoViewSet\nrouter = DefaultRouter()\nrouter.register(r"", AlumnoViewSet, basename="alumno")\nurlpatterns = router.urls\n',
    'modules/pagadores/urls.py': 'from rest_framework.routers import DefaultRouter\nfrom .views import PagadorViewSet\nrouter = DefaultRouter()\nrouter.register(r"", PagadorViewSet, basename="pagador")\nurlpatterns = router.urls\n',
    'modules/grupos/urls.py': 'from rest_framework.routers import DefaultRouter\nfrom .views import GrupoViewSet\nrouter = DefaultRouter()\nrouter.register(r"", GrupoViewSet, basename="grupo")\nurlpatterns = router.urls\n',
    'modules/asistencia/urls.py': 'from rest_framework.routers import DefaultRouter\nfrom .views import SesionViewSet\nrouter = DefaultRouter()\nrouter.register(r"", SesionViewSet, basename="sesion")\nurlpatterns = router.urls\n',
    'modules/pagos/urls.py': 'from rest_framework.routers import DefaultRouter\nfrom .views import PagoViewSet\nrouter = DefaultRouter()\nrouter.register(r"", PagoViewSet, basename="pago")\nurlpatterns = router.urls\n',
    'modules/documentos/urls.py': 'from rest_framework.routers import DefaultRouter\nfrom .views import DocumentoViewSet\nrouter = DefaultRouter()\nrouter.register(r"", DocumentoViewSet, basename="documento")\nurlpatterns = router.urls\n',
    'modules/authentication/urls.py': 'from django.urls import path\nfrom rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView\nfrom .views import RegisterView, ProfileView\n\nurlpatterns = [\n    path("register/", RegisterView.as_view(), name="auth-register"),\n    path("login/", TokenObtainPairView.as_view(), name="auth-login"),\n    path("token/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),\n    path("profile/", ProfileView.as_view(), name="auth-profile"),\n]\n',
}

for path, content in files.items():
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'OK: {path}')

print('Listo!')