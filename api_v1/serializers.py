import math
from rest_framework import serializers
from .models import (
    User, AbonnementFoyer, TypeDechet, GrilleTarifaireGrandCollecteur, 
    TransactionVenteDechet, AlerteSalubrite, EmplacementBac, Secteur, Quartier, NotificationQuartier
)


class QuartierSerializer(serializers.ModelSerializer):
    secteur_nom = serializers.ReadOnlyField(source='secteur.nom')

    class Meta:
        model = Quartier
        fields = ['id', 'nom', 'secteur', 'secteur_nom']

class SecteurSerializer(serializers.ModelSerializer):
    quartiers = QuartierSerializer(many=True, read_only=True)

    class Meta:
        model = Secteur
        fields = ['id', 'nom', 'commune_rattachee', 'quartiers']

class NotificationQuartierSerializer(serializers.ModelSerializer):
    quartier_nom = serializers.ReadOnlyField(source='quartier.nom')
    secteur_nom = serializers.ReadOnlyField(source='secteur.nom')

    class Meta:
        model = NotificationQuartier
        fields = ['id', 'titre', 'message', 'secteur', 'secteur_nom', 'quartier', 'quartier_nom', 'date_creation']

def calculer_distance_km(lat1, lon1, lat2, lon2):
    """ Calcule la distance en kilomètres entre deux points GPS """
    R = 6371  # Rayon de la terre en km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'telephone', 'longitude', 'latitude', 'commune_secteur', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class AbonnementFoyerSerializer(serializers.ModelSerializer):
    class Meta:
        model = AbonnementFoyer
        fields = '__all__'

class TypeDechetSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeDechet
        fields = '__all__'

class GrilleTarifaireGrandCollecteurSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrilleTarifaireGrandCollecteur
        fields = '__all__'

class TransactionVenteDechetSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionVenteDechet
        fields = '__all__'

class EmplacementBacSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmplacementBac
        fields = '__all__'

class AlerteSalubriteSerializer(serializers.ModelSerializer):
    signale_par_username = serializers.ReadOnlyField(source='signale_par.username')
    assigne_a_username = serializers.ReadOnlyField(source='assigne_a.username')
    # Pour afficher directement le nom du lieu dans l'API response
    lieu_intitule = serializers.ReadOnlyField() 

    class Meta:
        model = AlerteSalubrite
        fields = [
            'id', 'signale_par_username', 'photo', 'latitude', 'longitude', 
            'commune_secteur', 'description', 'date_signalement', 
            'statut', 'assigne_a_username', 'assigne_a', 'note_resolution',
            'emplacement_bac', 'lieu_intitule'
        ]
        read_only_fields = ['signale_par', 'date_signalement', 'lieu_intitule']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['signale_par'] = user

        lat = validated_data.get('latitude')
        lon = validated_data.get('longitude')
        bac_obj = validated_data.get('emplacement_bac')

        # Si aucun bac n'est explicitement sélectionné mais que le citoyen envoie des coordonnées, 
        # on cherche le bac officiel le plus proche (dans un rayon de 250 mètres)
        if not bac_obj and lat and lon:
            bacs = EmplacementBac.objects.all()
            plus_proche = None
            min_distance = float('inf')
            SEUIL_MAX_KM = 0.25  

            for bac in bacs:
                dist = calculer_distance_km(lat, lon, bac.latitude, bac.longitude)
                if dist < min_distance:
                    min_distance = dist
                    plus_proche = bac

            if plus_proche and min_distance <= SEUIL_MAX_KM:
                bac_obj = plus_proche

        # Attribution automatique du nom lisible pour la Mairie
        if bac_obj:
            validated_data['emplacement_bac'] = bac_obj
            validated_data['lieu_intitule'] = bac_obj.nom
            if not validated_data.get('commune_secteur'):
                validated_data['commune_secteur'] = bac_obj.commune_secteur
        else:
            if lat and lon:
                validated_data['lieu_intitule'] = f"Zone libre ({lat:.4f}, {lon:.4f})"
            else:
                validated_data['lieu_intitule'] = "Emplacement non spécifié"

        return super().create(validated_data)


from .models import CalendrierCollecte

class CalendrierCollecteSerializer(serializers.ModelSerializer):
    jour_libelle = serializers.CharField(source='get_jour_semaine_display', read_only=True)

    class Meta:
        model = CalendrierCollecte
        fields = '__all__'



