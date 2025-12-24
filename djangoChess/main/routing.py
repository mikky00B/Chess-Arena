from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # This URL pattern captures a "room_name" (the Game ID)
    # so two players in the same game ID are connected together.
    re_path(r"ws/chess/(?P<game_id>\w+)/$", consumers.ChessConsumer.as_asgi()),
]
