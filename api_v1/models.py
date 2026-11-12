from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Secteur(models.Model):
    nom = models.CharField(max_length=100, unique=True) # Ex: "Bertoua 1"
    commune_rattachee = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.nom

# 2. Modèle Quartier (rattaché à un Secteur)
class Quartier(models.Model):
    nom = models.CharField(max_length=100) # Ex: "Mokolo"
    secteur = models.ForeignKey(Secteur, on_delete=models.CASCADE, related_name='quartiers')

    class Meta:
        unique_together = ('nom', 'secteur')

    def __str__(self):
        return f"{self.nom} ({self.secteur.nom})"



class User(AbstractUser):
    ROLE_CHOICES = (
        ('foyer', 'Foyer / Citoyen'),
        ('institution', 'Mairie / Institution'),
        ('grand_collecteur', 'Grand Collecteur'),
    )
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='foyer')
    telephone = models.CharField(max_length=20, blank=True, null=True)
    secteur = models.ForeignKey(Secteur, on_delete=models.SET_NULL, null=True, blank=True)
    quartier = models.ForeignKey(Quartier, on_delete=models.SET_NULL, null=True, blank=True)
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class NotificationQuartier(models.Model):
    titre = models.CharField(max_length=200)
    message = models.TextField()
    secteur = models.ForeignKey(Secteur, on_delete=models.CASCADE)
    quartier = models.ForeignKey(Quartier, on_delete=models.CASCADE)
    emetteur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Avis Ramassage [{self.quartier.nom}] - {self.titre}"


class AbonnementFoyer(models.Model):
    foyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='abonnements_payes')
    petit_collecteur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='clients_abonnes')
    tarif_mensuel_fixe = models.DecimalField(max_digits=10, decimal_places=2, default=2000.00)
    date_debut = models.DateField(auto_now_add=True)
    statut_paiement = models.CharField(max_length=20, choices=(('actif', 'Actif/Payé'), ('suspendu', 'Impayé')), default='suspendu')

class TypeDechet(models.Model):
    nom = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nom

class GrilleTarifaireGrandCollecteur(models.Model):
    grand_collecteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='grille_tarifs')
    type_dechet = models.ForeignKey(TypeDechet, on_delete=models.CASCADE)
    prix_par_kg = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('grand_collecteur', 'type_dechet')

class TransactionVenteDechet(models.Model):
    petit_collecteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ventes_effectuees')
    grand_collecteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achats_effectues')
    type_dechet = models.ForeignKey(TypeDechet, on_delete=models.CASCADE)
    poids_en_kg = models.FloatField()
    montant_total = models.DecimalField(max_digits=10, decimal_places=2)
    date_transaction = models.DateTimeField(auto_now_add=True)
    reference_campay = models.CharField(max_length=100, blank=True, null=True)
    statut_paiement = models.CharField(max_length=20, choices=(('pending', 'En attente'), ('success', 'Réussi'), ('failed', 'Échoué')), default='pending')

# --- 💡 NOUVEAU MODÈLE : EMPLACEMENT DES BACS OFFICIELS ---
class EmplacementBac(models.Model):
    nom = models.CharField(max_length=255, verbose_name="Nom du lieu ou du bac (ex: Bac Carrefour Mvog-Mbi)")
    commune_secteur = models.CharField(max_length=100, verbose_name="Commune / Secteur (ex: Yaoundé 4)")
    latitude = models.FloatField(verbose_name="Latitude officielle")
    longitude = models.FloatField(verbose_name="Longitude officielle")

    def __str__(self):
        return f"{self.nom} ({self.commune_secteur})"

class AlerteSalubrite(models.Model):
    STATUT_CHOICES = (
        ('recue', 'Signalée / Reçue'),
        ('validee', 'Validée par la Mairie'),
        ('en_cours', 'En cours de ramassage (HYSACAM)'),
        ('resolue', 'Nettoyée / Résolue'),
        ('rejetee', 'Invalide / Rejetée'),
    )

    signale_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='alertes_envoyees')
    photo = models.ImageField(upload_to='alertes_dechets/')
    latitude = models.FloatField() # Coordonnées envoyées par le citoyen
    longitude = models.FloatField() # Coordonnées envoyées par le citoyen
    
    commune_secteur = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    date_signalement = models.DateTimeField(default=timezone.now)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='recue')
    
    # --- 💡 NOUVEAUX CHAMPS POUR STOCKER LE NOM LISIBLE DU LIEU ---
    emplacement_bac = models.ForeignKey(
        EmplacementBac, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='alertes'
    )
    lieu_intitule = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        verbose_name="Nom du lieu / Bac identifié pour la Mairie"
    )

    assigne_a = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        limit_choices_to={'role__in': ['institution', 'grand_collecteur']},
        related_name='alertes_a_traiter'
    )
    note_resolution = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Alerte de Salubrité"
        verbose_name_plural = "Alertes de Salubrité"
        ordering = ['-date_signalement']

    def __str__(self):
        lieu = self.lieu_intitule or self.commune_secteur or 'Zone inconnue'
        return f"Alerte #{self.id} - {lieu} ({self.get_statut_display()})"


class CalendrierCollecte(models.Model):
    JOURS_SEMAINE = [
        ('LUN', 'Lundi'),
        ('MAR', 'Mardi'),
        ('MER', 'Mercredi'),
        ('JEU', 'Jeudi'),
        ('VEN', 'Vendredi'),
        ('SAM', 'Samedi'),
        ('DIM', 'Dimanche'),
    ]

    commune_secteur = models.CharField(max_length=150, help_text="Ex: Yaoundé 4, Mvog-Mbi")
    jour_semaine = models.CharField(max_length=3, choices=JOURS_SEMAINE)
    heure_passage = models.TimeField(help_text="Heure prévue de passage du camion")
    type_dechet = models.CharField(max_length=100, default="Déchets ménagers", help_text="Ex: Ménagers, Recyclables, Encombrants")
    operateur = models.CharField(max_length=100, default="HYSACAM", help_text="Nom de l'entreprise ou opérateur")
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.commune_secteur} - {self.get_jour_semaine_display()} à {self.heure_passage} ({self.type_dechet})"


