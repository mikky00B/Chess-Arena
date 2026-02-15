from .models import SecurityEvent


def log_security_event(event_type, status="ok", user=None, game=None, details=None):
    SecurityEvent.objects.create(
        event_type=event_type,
        status=status,
        user=user,
        game=game,
        details=details or {},
    )
