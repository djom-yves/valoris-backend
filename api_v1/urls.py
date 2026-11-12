from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

router.register(r'users', views.UserViewSet)
router.register(r'abonnements', views.AbonnementFoyerViewSet)
router.register(r'types-dechets', views.TypeDechetViewSet)
router.register(r'grilles-tarifs', views.GrilleTarifaireGrandCollecteurViewSet)
router.register(r'transactions', views.TransactionVenteDechetViewSet)
router.register(r'alertes', views.AlerteSalubriteViewSet, basename='alerte')
router.register(r'bacs', views.EmplacementBacViewSet)
router.register(r'calendrier', views.CalendrierCollecteViewSet, basename='calendrier')

# 🟢 ROUTES MANQUANTES QUI PROVOQUAIENT LES ERREURS 404
router.register(r'secteurs', views.SecteurViewSet, basename='secteurs')
router.register(r'quartiers', views.QuartierViewSet, basename='quartiers')
router.register(r'notifications-quartier', views.NotificationQuartierViewSet, basename='notifications-quartier')

urlpatterns = [
    path('', include(router.urls)),
    path('cockpit/', views.cockpit_mairie, name='cockpit_mairie'),
    path('cockpit/assigner/<int:alerte_id>/', views.assigner_ordonnance, name='assigner_ordonnance'),
    path('hysacam/', views.cockpit_hysacam, name='cockpit_hysacam'),
    path('hysacam/cloturer/<int:alerte_id>/', views.cloturer_mission, name='cloturer_mission'),
]