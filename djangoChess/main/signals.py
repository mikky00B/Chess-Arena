from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Game, Profile
from .utils import calculate_elo  # We'll define this helper next


@receiver(post_save, sender=Game)
def update_rankings_on_game_end(sender, instance, created, **kwargs):
    if instance.is_active:
        return

    # Using a simple attribute check to prevent double-processing in the same instance
    if hasattr(instance, "_elo_processed"):
        return

    # Check for winner or draw condition
    is_draw = "draw" in instance.current_fen or "stalemate" in instance.current_fen

    if instance.winner or is_draw:
        white_profile = Profile.objects.get(user=instance.white_player)
        black_profile = Profile.objects.get(user=instance.black_player)

        # Determine Score
        if instance.winner == instance.white_player:
            score_white, score_black = 1, 0
        elif instance.winner == instance.black_player:
            score_white, score_black = 0, 1
        else:
            score_white, score_black = 0.5, 0.5

        # Calculate and Save
        white_profile.rating = calculate_elo(
            white_profile.rating, black_profile.rating, score_white
        )
        black_profile.rating = calculate_elo(
            black_profile.rating, white_profile.rating, score_black
        )

        white_profile.save()
        black_profile.save()

        # Mark as processed for this execution
        instance._elo_processed = True


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
