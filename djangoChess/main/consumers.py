import chess
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Game, Move
from .chess_logic import ChessGame
from django.utils import timezone


class ChessConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.game_id = self.scope["url_route"]["kwargs"]["game_id"]
        self.room_group_name = f"chess_{self.game_id}"
        self.user = self.scope["user"]

        if self.user.is_authenticated:
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Invalid JSON"}))
            return

        message_type = data.get("type")
        game_obj = await self.get_game()

        if message_type == "chat":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_broadcast",
                    "message": data.get("message"),
                    "player": self.user.username,
                },
            )

        elif message_type == "resign":
            if not game_obj.is_active:
                await self.send(text_data=json.dumps({"error": "Game already ended"}))
                return

            winner = (
                game_obj.black_player
                if self.user == game_obj.white_player
                else game_obj.white_player
            )
            await self.end_game_db(game_obj, "Resignation", winner)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "game_over_broadcast",
                    "outcome": f"{self.user.username} resigned.",
                    "winner": winner.username if winner else "Unknown",
                },
            )

        elif message_type == "move":
            if not game_obj.is_active or not game_obj.black_player:
                await self.send(text_data=json.dumps({"error": "Game not ready"}))
                return

            move_san = data.get("move")
            logic = ChessGame(game_obj.current_fen)
            is_white = self.user == game_obj.white_player
            is_black = self.user == game_obj.black_player
            current_turn = logic.board.turn

            # Validate it's the player's turn
            if (current_turn == chess.WHITE and not is_white) or (
                current_turn == chess.BLACK and not is_black
            ):
                await self.send(text_data=json.dumps({"error": "Not your turn!"}))
                return

            if logic.make_move(move_san):
                new_fen = logic.get_fen()
                outcome = logic.get_outcome()

                # Server-side time calculation
                updated_game = await self.update_game_data(
                    game_obj, move_san, new_fen, outcome, self.user
                )

                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chess_move_broadcast",
                        "move": move_san,
                        "fen": new_fen,
                        "player": self.user.username,
                        "outcome": outcome,
                        "white_time": float(updated_game.white_time),
                        "black_time": float(updated_game.black_time),
                        "is_active": updated_game.is_active,
                        "winner": (
                            updated_game.winner.username
                            if updated_game.winner
                            else None
                        ),
                    },
                )
            else:
                await self.send(text_data=json.dumps({"error": "Invalid Move"}))

    async def chat_broadcast(self, event):
        await self.send(
            text_data=json.dumps(
                {"type": "chat", "message": event["message"], "player": event["player"]}
            )
        )

    async def game_over_broadcast(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "game_over",
                    "outcome": event["outcome"],
                    "winner": event["winner"],
                }
            )
        )

    async def chess_move_broadcast(self, event):
        payload = event.copy()
        payload["type"] = "move"
        await self.send(text_data=json.dumps(payload))

    @database_sync_to_async
    def get_game(self):
        return Game.objects.select_related("white_player", "black_player").get(
            id=self.game_id
        )

    @database_sync_to_async
    def end_game_db(self, game_obj, outcome, winner):
        game_obj.is_active = False
        game_obj.winner = winner
        game_obj.save()

    @database_sync_to_async
    def update_game_data(self, game_obj, move_san, new_fen, outcome, current_player):
        now = timezone.now()

        # SERVER-SIDE TIME CALCULATION (CRITICAL FIX)
        if game_obj.last_move_timestamp:
            elapsed = (now - game_obj.last_move_timestamp).total_seconds()

            # Deduct time from the player who just moved
            current_turn_before_move = game_obj.current_fen.split()[1]
            if current_turn_before_move == "w":
                game_obj.white_time = max(0, float(game_obj.white_time) - elapsed)
            else:
                game_obj.black_time = max(0, float(game_obj.black_time) - elapsed)

        # Check for timeout
        if game_obj.white_time <= 0:
            game_obj.is_active = False
            game_obj.winner = game_obj.black_player
            outcome = "timeout"
        elif game_obj.black_time <= 0:
            game_obj.is_active = False
            game_obj.winner = game_obj.white_player
            outcome = "timeout"

        # Update game state
        game_obj.current_fen = new_fen
        game_obj.last_move_timestamp = now

        # Handle game outcome
        if outcome and outcome != "timeout":
            game_obj.is_active = False
            if outcome == "checkmate":
                game_obj.winner = current_player
            elif outcome in ["stalemate", "draw_material", "draw"]:
                game_obj.winner = None  # Draw

        game_obj.save()

        # Record move
        Move.objects.create(
            game=game_obj, move_san=move_san, move_number=game_obj.moves.count() + 1
        )

        return game_obj
