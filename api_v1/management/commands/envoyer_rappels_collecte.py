from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from api_v1.models import CalendrierCollecte, Notification  # Remplace 'myapp' par le nom de ton app

class Command(BaseCommand):
    help = "Génère automatiquement des notifications de rappel la veille des jours de collecte."

    def handle(self, *args, **options):
        # 1. Déterminer le jour de demain (ex: 'LUN', 'MAR', etc.)
        demain = timezone.now().date() + timedelta(days=1)
        jours_mapping = {
            0: 'LUN', 1: 'MAR', 2: 'MER', 3: 'JEU', 
            4: 'VEN', 5: 'SAM', 6: 'DIM'
        }
        code_jour_demain = jours_mapping[demain.weekday()]

        # 2. Rechercher dans le calendrier les collectes prévues demain
        collectes_demain = CalendrierCollecte.objects.filter(jour_semaine=code_jour_demain)

        if not collectes_demain.exists():
            self.stdout.write(self.style.WARNING("Aucune collecte prévue pour demain."))
            return

        count = 0
        for collecte in collectes_demain:
            secteur = collecte.commune_secteur
            
            # 3. Créer la notification pour ce secteur
            titre = "Rappel Collecte HYSACAM 🚛"
            message = (
                f"Demain ({collecte.get_jour_semaine_display()}) à {collecte.heure_passage}, "
                f"passage prévu pour vos {collecte.type_dechet} dans le secteur de {secteur}. "
                f"Pensez à sortir vos bacs !"
            )

            # Évite les doublons si la notification a déjà été générée aujourd'hui
            deja_envoyee = Notification.objects.filter(
                commune_secteur=secteur,
                titre=titre,
                date_creation__date=timezone.now().date()
            ).exists()

            if not deja_envoyee:
                Notification.objects.create(
                    commune_secteur=secteur,
                    titre=titre,
                    message=message
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f"Succès : {count} rappels automatiques générés pour les collectes de demain."))

