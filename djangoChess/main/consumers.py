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
        data = json.loads(text_data)
        message_type = data.get("type")

        # 1. Fetch current state from DB
        game_obj = await self.get_game()

        # --- BRANCH 1: LIVE CHAT ---
        if message_type == "chat":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_broadcast",
                    "message": data.get("message"),
                    "player": self.user.username,
                },
            )

        # --- BRANCH 2: RESIGN ---
        elif message_type == "resign":
            outcome = "Resignation"
            winner = (
                game_obj.black_player
                if self.user == game_obj.white_player
                else game_obj.white_player
            )
            await self.end_game_db(game_obj, outcome, winner)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "game_over_broadcast",
                    "outcome": f"{self.user.username} resigned.",
                    "winner": winner.username,
                },
            )

        # --- BRANCH 3: CHESS MOVE ---
        elif message_type == "move":
            if not game_obj.is_active:
                await self.send(text_data=json.dumps({"error": "Game is over."}))
                return

            # CHECK: Is there an opponent yet?
            if not game_obj.black_player:
                await self.send(
                    text_data=json.dumps({"error": "Waiting for opponent to join..."})
                )
                return

            move_san = data.get("move")
            logic = ChessGame(game_obj.current_fen)

            # STRICT COLOR CHECK
            is_white = self.user == game_obj.white_player
            is_black = self.user == game_obj.black_player

            if (logic.board.turn == chess.WHITE and not is_white) or (
                logic.board.turn == chess.BLACK and not is_black
            ):
                await self.send(
                    text_data=json.dumps({"error": "Not your turn or your piece!"})
                )
                return

            if logic.make_move(move_san):
                new_fen = logic.get_fen()
                outcome = logic.get_outcome()

                # Update DB (Calculates time and saves FEN)
                updated_game = await self.update_game_data(
                    game_obj, move_san, new_fen, outcome
                )

                # Broadcast to EVERYONE (Syncs the UI)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chess_move_broadcast",
                        "move": move_san,
                        "fen": new_fen,
                        "player": self.user.username,
                        "outcome": outcome,
                        "white_time": updated_game.white_time,
                        "black_time": updated_game.black_time,
                    },
                )
            else:
                await self.send(text_data=json.dumps({"error": "Invalid Move"}))

    # --- BROADCAST HANDLERS ---

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
        await self.send(
            text_data=json.dumps(
                {
                    "type": "move",
                    "move": event["move"],
                    "fen": event["fen"],
                    "player": event["player"],
                    "outcome": event["outcome"],
                    "white_time": event["white_time"],
                    "black_time": event["black_time"],
                }
            )
        )

    # --- DATABASE HELPERS ---

    @database_sync_to_async
    def get_game(self):
        # select_related pulls the player objects into memory immediately
        return Game.objects.select_related("white_player", "black_player").get(
            id=self.game_id
        )

    @database_sync_to_async
    def end_game_db(self, game_obj, outcome, winner):
        game_obj.is_active = False
        game_obj.winner = winner
        game_obj.save()

    @database_sync_to_async
    def update_game_data(self, game_obj, move_san, new_fen, outcome):
        now = timezone.now()

        # TIMER LOGIC: Only start deducting if Black has joined and this isn't the first move
        if game_obj.black_player and game_obj.last_move_timestamp:
            time_spent = (now - game_obj.last_move_timestamp).total_seconds()
            if "w" in game_obj.current_fen:
                game_obj.white_time -= time_spent
            else:
                game_obj.black_time -= time_spent

        game_obj.last_move_timestamp = now
        game_obj.current_fen = new_fen

        if outcome:
            game_obj.is_active = False
            if outcome == "checkmate":
                game_obj.winner = self.user

        game_obj.save()
        Move.objects.create(
            game=game_obj, move_san=move_san, move_number=game_obj.moves.count() + 1
        )
        return game_obj
