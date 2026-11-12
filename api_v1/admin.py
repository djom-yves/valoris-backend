from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, Secteur, Quartier, CalendrierCollecte, AbonnementFoyer, 
    TypeDechet, EmplacementBac, GrilleTarifaireGrandCollecteur, 
    TransactionVenteDechet, AlerteSalubrite
)

class CustomUserAdmin(UserAdmin):
    # Champs affichés lors de la modification d'un utilisateur existant
    fieldsets = UserAdmin.fieldsets + (
        ('Informations Valoris (Smart City)', {'fields': ('role', 'telephone', 'longitude', 'latitude', 'secteur', 'quartier')}),
    )
    
    # Champs affichés lors de la création (ajout) d'un nouvel utilisateur
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Informations Valoris (Smart City)', {
            'fields': ('role', 'telephone', 'secteur', 'quartier', 'longitude', 'latitude'),
        }),
    )

    list_display = ['username', 'email', 'role', 'telephone', 'secteur', 'quartier', 'is_staff']
    list_filter = ['role', 'secteur', 'quartier', 'is_staff']

# 🟢 Enregistrement des nouveaux modèles Secteur et Quartier pour la gestion par la Mairie
@admin.register(Secteur)
class SecteurAdmin(admin.ModelAdmin):
    list_display = ['nom', 'commune_rattachee']
    search_fields = ['nom', 'commune_rattachee']

@admin.register(Quartier)
class QuartierAdmin(admin.ModelAdmin):
    list_display = ['nom', 'secteur']
    list_filter = ['secteur']
    search_fields = ['nom']

# Enregistrement des autres modèles sur l'interface d'administration
admin.site.register(User, CustomUserAdmin)
admin.site.register(AbonnementFoyer)
admin.site.register(TypeDechet)
admin.site.register(GrilleTarifaireGrandCollecteur)
admin.site.register(TransactionVenteDechet)
admin.site.register(AlerteSalubrite)
admin.site.register(EmplacementBac)
admin.site.register(CalendrierCollecte)