from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Game, Profile
from .utils import calculate_elo
from .blockchain_utils import generate_winner_signature, generate_draw_signature


@receiver(post_save, sender=Game)
def update_rankings_on_game_end(sender, instance, created, **kwargs):
    """
    Update ELO ratings and generate blockchain signatures when game ends.
    """
    if instance.is_active:
        return

    # Prevent double-processing
    if hasattr(instance, "_elo_processed"):
        return

    # Need both players for rating updates
    if not instance.white_player or not instance.black_player:
        return

    # Determine outcome
    is_draw = instance.winner is None and not instance.is_active

    # Only process if there's a clear outcome
    if instance.winner or is_draw:
        white_profile = Profile.objects.get(user=instance.white_player)
        black_profile = Profile.objects.get(user=instance.black_player)

        # Determine scores for ELO calculation
        if instance.winner == instance.white_player:
            score_white, score_black = 1, 0
        elif instance.winner == instance.black_player:
            score_white, score_black = 0, 1
        else:
            score_white, score_black = 0.5, 0.5

        # Calculate and save new ratings
        new_white_rating = calculate_elo(
            white_profile.rating, black_profile.rating, score_white
        )
        new_black_rating = calculate_elo(
            black_profile.rating, white_profile.rating, score_black
        )

        white_profile.rating = new_white_rating
        black_profile.rating = new_black_rating

        white_profile.save()
        black_profile.save()

        # Generate blockchain signature for winner or draw
        try:
            if instance.winner:
                # Check if winner has an Ethereum address stored
                winner_profile = Profile.objects.get(user=instance.winner)
                if (
                    hasattr(winner_profile, "ethereum_address")
                    and winner_profile.ethereum_address
                ):
                    v, r, s = generate_winner_signature(
                        instance.id, winner_profile.ethereum_address
                    )
                    # Store signature for later claim
                    instance.signature_v = v
                    instance.signature_r = r
                    instance.signature_s = s
                    instance.save(
                        update_fields=["signature_v", "signature_r", "signature_s"]
                    )
            else:
                # Draw - generate draw signature
                v, r, s = generate_draw_signature(instance.id)
                instance.signature_v = v
                instance.signature_r = r
                instance.signature_s = s
                instance.save(
                    update_fields=["signature_v", "signature_r", "signature_s"]
                )

        except Exception as e:
            # Log error but don't fail the entire transaction
            print(f"Error generating blockchain signature: {e}")

        # Mark as processed
        instance._elo_processed = True


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create profile for new users."""
    if created:
        Profile.objects.create(user=instance)
