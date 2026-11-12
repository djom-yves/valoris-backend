from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.functions import Coalesce

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from .models import (
    User, AbonnementFoyer, TypeDechet, 
    GrilleTarifaireGrandCollecteur, TransactionVenteDechet, AlerteSalubrite, EmplacementBac
)
from .serializers import (
    UserSerializer, AbonnementFoyerSerializer, TypeDechetSerializer,
    GrilleTarifaireGrandCollecteurSerializer, TransactionVenteDechetSerializer, 
    AlerteSalubriteSerializer, EmplacementBacSerializer
)

# Fonction utilitaire de distance pour le tri des bacs
def calculer_distance_km(lat1, lon1, lat2, lon2):
    import math
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# =====================================================================
# 🛡️ DÉCORATEURS DE SÉCURITÉ POUR LES VUES WEB (MAIRIE & HYSACAM)
# =====================================================================
def role_requis(roles_autorises=[]):
    def decorator(view_func):
        def wrap(request, *args, **kwargs):
            if request.user.is_authenticated and request.user.role in roles_autorises:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, "🛡️ Zone sécurisée : Vos privilèges ne vous permettent pas d'accéder à cet espace.")
                return redirect('admin:index')
        return wrap
    return decorator


# =====================================================================
# 📱 API VIEWSETS (REST FRAMEWORK POUR L'APPLICATION FLUTTER)
# =====================================================================

from rest_framework.permissions import AllowAny, IsAuthenticated # type: ignore

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        # 🟢 Autoriser l'accès libre (sans token) uniquement pour l'inscription (create) et la connexion (login_user)
        if self.action in ['create', 'login']:
            return [AllowAny()]
        # Pour toutes les autres actions (lister les utilisateurs, modifier, etc.), l'authentification reste obligatoire
        return [IsAuthenticated()]

    @action(detail=False, methods=['post'], url_path='login')
    def login(self, request):  # 👈 Renommé de login_user à login
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {'error': 'Veuillez fournir un nom d\'utilisateur et un mot de passe.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(username=username, password=password)

        if user is not None:
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'role': getattr(user, 'role', 'Utilisateur'),
                    'telephone': getattr(user, 'telephone', '')
                }
            }, status=status.HTTP_200_OK)
        else:
            return Response(
                {'error': 'Identifiants invalides.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )


     # 🟢 NOUVELLE ACTION POUR CRÉER UN GRAND COLLECTEUR DEPUIS LA MAIRIE
    @action(detail=False, methods=['post'], url_path='creer_grand_collecteur')
    def creer_grand_collecteur(self, request):
        user = request.user
        
        # Seule la Mairie (institution) peut créer un grand collecteur pour sa zone
        if user.role != 'institution':
            return Response({"error": "Action réservée aux mairies."}, status=status.HTTP_403_FORBIDDEN)

        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({"error": "Le nom d'utilisateur et le mot de passe sont obligatoires."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({"error": "Ce nom d'utilisateur existe déjà."}, status=status.HTTP_400_BAD_REQUEST)

        # Création rattachée automatiquement à la commune de la Mairie connectée
        nouveau_collecteur = User.objects.create_user(
            username=username,
            password=password,
            role='grand_collecteur',
            commune_secteur=getattr(user, 'commune_secteur', '')
        )

        return Response({
            "message": f"Grand collecteur {nouveau_collecteur.username} créé avec succès !",
            "id": nouveau_collecteur.id,
            "username": nouveau_collecteur.username
        }, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save()
        


class AbonnementFoyerViewSet(viewsets.ModelViewSet):
    queryset = AbonnementFoyer.objects.all()
    serializer_class = AbonnementFoyerSerializer


class TypeDechetViewSet(viewsets.ModelViewSet):
    queryset = TypeDechet.objects.all()
    serializer_class = TypeDechetSerializer


class GrilleTarifaireGrandCollecteurViewSet(viewsets.ModelViewSet):
    queryset = GrilleTarifaireGrandCollecteur.objects.all()
    serializer_class = GrilleTarifaireGrandCollecteurSerializer


class TransactionVenteDechetViewSet(viewsets.ModelViewSet):
    queryset = TransactionVenteDechet.objects.all()
    serializer_class = TransactionVenteDechetSerializer


# --- 💡 NOUVEAU VIEWSET POUR GÉRER LES BACS CÔTÉ CITOYEN ---
class EmplacementBacViewSet(viewsets.ModelViewSet):
    queryset = EmplacementBac.objects.all()
    serializer_class = EmplacementBacSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='proches')
    def bacs_proches(self, request):
        """
        Renvoie la liste des bacs à ordures triée du plus proche au plus lointain 
        en fonction de la latitude et longitude transmises par le citoyen.
        """
        lat_str = request.query_params.get('latitude')
        lon_str = request.query_params.get('longitude')
        
        bacs = EmplacementBac.objects.all()
        if not lat_str or not lon_str:
            serializer = self.get_serializer(bacs, many=True)
            return Response(serializer.data)

        try:
            user_lat = float(lat_str)
            user_lon = float(lon_str)
        except ValueError:
            return Response({"error": "Coordonnées GPS invalides."}, status=400)

        bacs_avec_distance = []
        for bac in bacs:
            dist = calculer_distance_km(user_lat, user_lon, bac.latitude, bac.longitude)
            bacs_avec_distance.append((bac, dist))

        # Tri par ordre croissant de distance
        bacs_avec_distance.sort(key=lambda x: x[1])

        result = []
        for bac, dist in bacs_avec_distance:
            data = EmplacementBacSerializer(bac).data
            data['distance_km'] = round(dist, 2)
            result.append(data)

        return Response(result, status=status.HTTP_200_OK)


class AlerteSalubriteViewSet(viewsets.ModelViewSet):
    serializer_class = AlerteSalubriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return AlerteSalubrite.objects.all()
            
        # Inclure tous les rôles citoyens / pré-collecte qui signalent des alertes
        if user.role in ['foyer', 'citoyen', 'petit_collecteur']:
            return AlerteSalubrite.objects.filter(signale_par=user)
            
        elif user.role == 'institution':
            # On s'assure de récupérer les alertes de la commune (insensible à la casse)
            secteur_mairie = user.commune_secteur or ""
            return AlerteSalubrite.objects.filter(
                commune_secteur__iexact=secteur_mairie
            ).order_by('-date_signalement')
        
        elif user.role == 'grand_collecteur':
            return AlerteSalubrite.objects.filter(assigne_a=user)
            
        # Par défaut si aucun rôle ne correspond mais qu'il est authentifié, on évite le blocage total
        return AlerteSalubrite.objects.filter(signale_par=user)

    @action(detail=True, methods=['post'], url_path='assigner')
    def assigner_alerte(self, request, pk=None):
        alerte = self.get_object()
        if request.user.role != 'institution':
            return Response({"error": "Action réservée aux mairies et institutions."}, status=403)
        
        id_collecteur = request.data.get('assigne_a_id')
        if not id_collecteur:
            return Response({"error": "Veuillez fournir l'ID du collecteur (assigne_a_id)."}, status=400)

        alerte.assigne_a_id = id_collecteur
        alerte.statut = 'validee'
        alerte.save()
        
        return Response({
            "message": f"Alerte assignée avec succès à {alerte.assigne_a.username}.",
            "statut": alerte.statut
        })

    # Dans views.py, à l'intérieur de la classe AlerteSalubriteViewSet :

    @action(detail=False, methods=['get'], url_path='itineraire_optimise')
    def itineraire_optimise(self, request):
        """
        Génère une feuille de route optimisée (itinéraire le plus court)
        pour le ramassage des alertes/bacs validés d'un secteur.
        
        Paramètres GET optionnels :
        - lat_depart : Latitude du dépôt/camion (ex: 3.8480)
        - lon_depart : Longitude du dépôt/camion (ex: 11.5021)
        """
        user = request.user

        # 1. Filtrer les alertes à ramasser (statut 'validee' ou 'en_cours')
        if user.role == 'grand_collecteur':
            alertes_qs = AlerteSalubrite.objects.filter(assigne_a=user, statut__in=['validee', 'en_cours'])
        elif user.role == 'institution':
            alertes_qs = AlerteSalubrite.objects.filter(commune_secteur=user.commune_secteur, statut__in=['validee', 'en_cours'])
        else:
            alertes_qs = AlerteSalubrite.objects.filter(statut__in=['validee', 'en_cours'])

        alertes = list(alertes_qs)

        if not alertes:
            return Response({
                "message": "Aucune alerte à ramasser pour le moment.",
                "itineraire": [],
                "distance_totale_km": 0
            }, status=status.HTTP_200_OK)

        # 2. Récupérer le point de départ du camion (ou utiliser le premier point de la liste)
        lat_depart = request.query_params.get('lat_depart')
        lon_depart = request.query_params.get('lon_depart')

        if lat_depart and lon_depart:
            curr_lat = float(lat_depart)
            curr_lon = float(lon_depart)
        else:
            # Point de départ par défaut = la première alerte
            curr_lat = alertes[0].latitude
            curr_lon = alertes[0].longitude

        # 3. Algorithme du Plus Proche Voisin (Nearest Neighbor Algorithm)
        points_a_visiter = alertes.copy()
        itineraire_ordonne = []
        distance_totale_km = 0.0

        while points_a_visiter:
            plus_proche = None
            dist_min = float('inf')

            for alerte in points_a_visiter:
                dist = calculer_distance_km(curr_lat, curr_lon, alerte.latitude, alerte.longitude)
                if dist < dist_min:
                    dist_min = dist
                    plus_proche = alerte

            if plus_proche:
                # Ajout de l'étape ordonnée
                itineraire_ordonne.append({
                    "ordre_passage": len(itineraire_ordonne) + 1,
                    "alerte_id": plus_proche.id,
                    "lieu": plus_proche.lieu_intitule or plus_proche.commune_secteur or f"Alerte #{plus_proche.id}",
                    "latitude": plus_proche.latitude,
                    "longitude": plus_proche.longitude,
                    "statut": plus_proche.statut,
                    "distance_depuis_etape_precedente_km": round(dist_min, 2)
                })
                
                distance_totale_km += dist_min
                curr_lat = plus_proche.latitude
                curr_lon = plus_proche.longitude
                points_a_visiter.remove(plus_proche)

        return Response({
            "commune_secteur": getattr(user, 'commune_secteur', 'Global'),
            "nombre_etapes": len(itineraire_ordonne),
            "distance_totale_estimee_km": round(distance_totale_km, 2),
            "feuille_de_route": itineraire_ordonne
        }, status=status.HTTP_200_OK)


    @action(detail=False, methods=['get'], url_path='statistiques')
    def statistiques_commune(self, request):
        user = request.user
        
        # 🟢 Utilisation sécurisée de la relation secteur si elle existe
        if user.role == 'institution' and hasattr(user, 'secteur') and user.secteur:
            alertes_qs = AlerteSalubrite.objects.filter(commune_secteur__iexact=user.secteur.nom)
            bacs_qs = EmplacementBac.objects.filter(commune_secteur__iexact=user.secteur.nom)
        else:
            alertes_qs = AlerteSalubrite.objects.all()
            bacs_qs = EmplacementBac.objects.all()

        total_alertes = alertes_qs.count()

        if total_alertes == 0:
            return Response({
                "message": "Aucune donnée disponible pour le moment.",
                "total_alertes": 0,
                "taux_resolution_pourcent": 0
            }, status=status.HTTP_200_OK)

        stats_statut = alertes_qs.aggregate(
            recue=Count('id', filter=Q(statut='recue')),
            validee=Count('id', filter=Q(statut='validee')),
            en_cours=Count('id', filter=Q(statut='en_cours')),
            resolue=Count('id', filter=Q(statut='resolue')),
            rejetee=Count('id', filter=Q(statut='rejetee'))
        )

        alertes_resolues = stats_statut['resolue']
        taux_resolution = round((alertes_resolues / total_alertes) * 100, 2)

        points_noirs = alertes_qs.annotate(
                zone_nom=Coalesce('lieu_intitule', 'commune_secteur')
            ).values('zone_nom').annotate(
                nb_alertes=Count('id')
            ).order_by('-nb_alertes')

        return Response({
            "commune_secteur": user.secteur.nom if (user.role == 'institution' and hasattr(user, 'secteur') and user.secteur) else 'Toutes les communes',
            "total_alertes_signalees": total_alertes,
            "taux_resolution_pourcent": taux_resolution,
            "repartition_par_statut": {
                "signalées_non_traitees": stats_statut['recue'],
                "validees_par_mairie": stats_statut['validee'],
                "en_cours_ramassage": stats_statut['en_cours'],
                "resolues_nettoyees": stats_statut['resolue'],
                "rejetees": stats_statut['rejetee']
            },
            "top_points_noirs": list(points_noirs),
            "nombre_total_bacs_officiels": bacs_qs.count()
        }, status=status.HTTP_200_OK)


# =====================================================================
# 💻 VUES WEB RESPONSIVES (PORTAIL TEMPLATES DJANGO + BOOTSTRAP 5)
# =====================================================================

@login_required
@role_requis(roles_autorises=['institution'])
def cockpit_mairie(request):
    alertes = AlerteSalubrite.objects.filter(
        commune_secteur=request.user.commune_secteur
    ).order_by('-date_signalement')

    collecteurs = User.objects.filter(role='grand_collecteur')

    context = {
        'alertes': alertes,
        'collecteurs': collecteurs,
        'mairie_nom': request.user.commune_secteur or "Municipale"
    }
    return render(request, 'api_v1/cockpit_mairie.html', context)


@login_required
@role_requis(roles_autorises=['institution'])
def assigner_ordonnance(request, alerte_id):
    if request.method == 'POST':
        alerte = get_object_or_404(AlerteSalubrite, id=alerte_id, commune_secteur=request.user.commune_secteur)
        collecteur_id = request.POST.get('collecteur_id')
        
        if collecteur_id:
            alerte.assigne_a_id = collecteur_id
            alerte.statut = 'en_cours'  
            alerte.save()
            messages.success(request, f"L'alerte #{alerte.id} a été assignée avec succès pour intervention.")
            
    return redirect('cockpit_mairie')


@login_required
@role_requis(roles_autorises=['grand_collecteur'])
def cockpit_hysacam(request):
    missions = AlerteSalubrite.objects.filter(
        assigne_a=request.user
    ).order_by('-date_signalement')
    missions_en_cours = missions.filter(statut='en_cours').count()

    context = {
        'missions': missions,
        'missions_en_cours': missions_en_cours,
    }
    return render(request, 'api_v1/cockpit_hysacam.html', context)


@login_required
@role_requis(roles_autorises=['grand_collecteur'])
def cloturer_mission(request, alerte_id):
    if request.method == 'POST':
        alerte = get_object_or_404(AlerteSalubrite, id=alerte_id, assigne_a=request.user)
        alerte.statut = 'resolue'
        alerte.save()
        messages.success(request, f"🚀 Mission #{alerte.id} clôturée ! Le secteur est de nouveau propre.")
    return redirect('cockpit_hysacam')


from .models import CalendrierCollecte
from .serializers import CalendrierCollecteSerializer

class CalendrierCollecteViewSet(viewsets.ModelViewSet):
    queryset = CalendrierCollecte.objects.all().order_by('commune_secteur', 'jour_semaine')
    serializer_class = CalendrierCollecteSerializer

    def get_queryset(self):
        """
        Permet de filtrer le calendrier par secteur via l'URL :
        ex: /api/v1/calendrier/?secteur=Yaoundé 4
        """
        queryset = super().get_queryset()
        secteur = self.request.query_params.get('secteur', None)
        if secteur:
            queryset = queryset.filter(commune_secteur__icontains=secteur)
        return queryset


from rest_framework import viewsets, permissions, status
from .models import Secteur, Quartier, NotificationQuartier
from .serializers import SecteurSerializer, QuartierSerializer, NotificationQuartierSerializer

# 1. Gestion des Secteurs & Quartiers
class SecteurViewSet(viewsets.ModelViewSet):
    queryset = Secteur.objects.all()
    serializer_class = SecteurSerializer
    permission_classes = [permissions.AllowAny] # Permet aux citoyens de lire la liste à l'inscription

class QuartierViewSet(viewsets.ModelViewSet):
    queryset = Quartier.objects.all()
    serializer_class = QuartierSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()
        secteur_id = self.request.query_params.get('secteur_id')
        if secteur_id:
            # 🟢 Filtre dynamique : ne renvoie que les quartiers du secteur sélectionné !
            queryset = queryset.filter(secteur_id=secteur_id)
        return queryset

# 2. Diffusion et Réception des Notifications de Ramassage
class NotificationQuartierViewSet(viewsets.ModelViewSet):
    queryset = NotificationQuartier.objects.all().order_by('-date_creation')
    serializer_class = NotificationQuartierSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # 🟢 FILTRAGE STRICT : Si c'est un citoyen, il ne reçoit QUE les alertes de son quartier exact
        if user.role == 'foyer' and user.quartier:
            return NotificationQuartier.objects.filter(quartier=user.quartier).order_by('-date_creation')
        
        # Pour la Mairie ou le Grand Collecteur, ils voient l'historique complet
        return super().get_queryset()

    def perform_create(self, serializer):
        # Assigne la Mairie/Collecteur connecté comme auteur de la notification
        serializer.save(emetteur=self.request.user)


