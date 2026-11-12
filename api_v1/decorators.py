# api_v1/decorators.py
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages

def role_requis(roles_autorises=[]):
    """ Décorateur pour vérifier le rôle exact de l'utilisateur (institution, grand_collecteur, etc.) """
    def decorator(view_func):
        def wrap(request, *args, **kwargs):
            if request.user.is_authenticated and request.user.role in roles_autorises:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, "🛡️ Zone sécurisée : Vos privilèges actuels ne vous permettent pas d'accéder à cet espace.")
                # Redirection vers une page sûre en cas de tentative de fraude
                return redirect('admin:index') 
        return wrap
    return decorator


