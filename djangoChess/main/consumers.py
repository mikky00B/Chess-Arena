import chess
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Game, Move
from .chess_logic import ChessGame
from django.utils import timezone
from django.db.models import Q
from .timer_sync import sync_game_clock


class ChessConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.game_id = int(self.scope["url_route"]["kwargs"]["game_id"])
        self.room_group_name = f"chess_{self.game_id}"
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        if not await self.is_game_participant():
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self.send_state_sync()

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
        if not game_obj:
            await self.send(text_data=json.dumps({"error": "Game not found"}))
            return

        if self.user not in [game_obj.white_player, game_obj.black_player]:
            await self.send(text_data=json.dumps({"error": "Not authorized for this game"}))
            return

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
            await self.end_game_db(game_obj, "resignation", winner)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "game_over_broadcast",
                    "outcome": "resignation",
                    "winner": winner.username if winner else "Unknown",
                },
            )

        elif message_type == "offer_draw":
            if not game_obj.is_active or not game_obj.black_player:
                await self.send(text_data=json.dumps({"error": "Cannot offer draw"}))
                return

            await self.set_draw_offer(game_obj, self.user)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "draw_offer_broadcast",
                    "player": self.user.username,
                },
            )

        elif message_type == "accept_draw":
            if not game_obj.is_active or not game_obj.draw_offered_by:
                await self.send(
                    text_data=json.dumps({"error": "No draw offer to accept"})
                )
                return

            if self.user == game_obj.draw_offered_by:
                await self.send(
                    text_data=json.dumps({"error": "Cannot accept your own offer"})
                )
                return

            await self.end_game_db(game_obj, "draw by agreement", None)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "game_over_broadcast",
                    "outcome": "draw by agreement",
                    "winner": None,
                },
            )

        elif message_type == "decline_draw":
            await self.set_draw_offer(game_obj, None)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "draw_declined_broadcast",
                },
            )

        elif message_type == "move":
            if not game_obj.is_active or not game_obj.black_player:
                await self.send(
                    text_data=json.dumps(
                        {"error": "Game not ready", "fen": game_obj.current_fen}
                    )
                )
                return

            move_san = data.get("move")
            logic = ChessGame(game_obj.current_fen)
            is_white = self.user == game_obj.white_player
            is_black = self.user == game_obj.black_player
            current_turn = logic.board.turn

            if (current_turn == chess.WHITE and not is_white) or (
                current_turn == chess.BLACK and not is_black
            ):
                await self.send(
                    text_data=json.dumps(
                        {"error": "Not your turn!", "fen": game_obj.current_fen}
                    )
                )
                return

            if logic.make_move(move_san):
                new_fen = logic.get_fen()
                outcome = logic.get_outcome()

                update_result = await self.update_game_data(
                    game_obj, move_san, new_fen, outcome, self.user
                )
                updated_game = update_result["game"]
                resolved_outcome = update_result["outcome"]
                if not update_result["move_applied"] and resolved_outcome == "timeout":
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "game_over_broadcast",
                            "outcome": "timeout",
                            "winner": (
                                updated_game.winner.username if updated_game.winner else None
                            ),
                        },
                    )
                    return

                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chess_move_broadcast",
                        "move": move_san,
                        "fen": new_fen,
                        "player": self.user.username,
                        "outcome": resolved_outcome,
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
                await self.send(
                    text_data=json.dumps(
                        {"error": "Invalid Move", "fen": game_obj.current_fen}
                    )
                )
        elif message_type == "sync_state":
            await self.send_state_sync()
        else:
            await self.send(text_data=json.dumps({"error": "Unknown message type"}))

    async def send_state_sync(self):
        synced_game = await self.sync_and_get_game_state()
        if not synced_game:
            return
        if not synced_game.is_active:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "state_sync",
                        "fen": synced_game.current_fen,
                        "white_time": float(synced_game.white_time),
                        "black_time": float(synced_game.black_time),
                        "game_started": bool(synced_game.last_move_timestamp),
                        "is_active": False,
                        "winner": synced_game.winner.username if synced_game.winner else None,
                        "outcome": "timeout"
                        if (synced_game.white_time <= 0 or synced_game.black_time <= 0)
                        else None,
                    }
                )
            )
            return

        await self.send(
            text_data=json.dumps(
                {
                    "type": "state_sync",
                    "fen": synced_game.current_fen,
                    "white_time": float(synced_game.white_time),
                    "black_time": float(synced_game.black_time),
                    "game_started": bool(synced_game.last_move_timestamp),
                    "is_active": True,
                    "winner": None,
                }
            )
        )

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

    async def draw_offer_broadcast(self, event):
        await self.send(
            text_data=json.dumps({"type": "draw_offer", "player": event["player"]})
        )

    async def draw_declined_broadcast(self, event):
        await self.send(text_data=json.dumps({"type": "draw_declined"}))

    @database_sync_to_async
    def get_game(self):
        return (
            Game.objects.select_related("white_player", "black_player", "draw_offered_by")
            .filter(id=self.game_id)
            .first()
        )

    @database_sync_to_async
    def sync_and_get_game_state(self):
        game_obj = (
            Game.objects.select_related("white_player", "black_player", "winner")
            .filter(id=self.game_id)
            .first()
        )
        if not game_obj:
            return None
        sync_result = sync_game_clock(game_obj)
        if sync_result["changed"]:
            update_fields = ["white_time", "black_time", "last_move_timestamp"]
            if sync_result["timed_out"]:
                update_fields.extend(["is_active", "winner", "draw_offered_by"])
            game_obj.save(update_fields=update_fields)
        return game_obj

    @database_sync_to_async
    def is_game_participant(self):
        return Game.objects.filter(id=self.game_id).filter(
            Q(white_player=self.user) | Q(black_player=self.user)
        ).exists()

    @database_sync_to_async
    def end_game_db(self, game_obj, outcome, winner):
        game_obj.is_active = False
        game_obj.winner = winner
        game_obj.draw_offered_by = None
        game_obj.save()

    @database_sync_to_async
    def set_draw_offer(self, game_obj, user):
        game_obj.draw_offered_by = user
        game_obj.save()

    @database_sync_to_async
    def update_game_data(self, game_obj, move_san, new_fen, outcome, current_player):
        now = timezone.now()
        if game_obj.black_player and not game_obj.last_move_timestamp:
            game_obj.last_move_timestamp = now

        sync_result = sync_game_clock(game_obj, now=now)
        elapsed = sync_result["elapsed"]
        if sync_result["timed_out"]:
            outcome = "timeout"
            game_obj.save(update_fields=["white_time", "black_time", "last_move_timestamp", "is_active", "winner", "draw_offered_by"])
            return {"game": game_obj, "outcome": outcome, "move_applied": False}

        game_obj.current_fen = new_fen
        game_obj.last_move_timestamp = now

        if game_obj.draw_offered_by:
            game_obj.draw_offered_by = None

        if outcome and outcome != "timeout":
            game_obj.is_active = False
            if outcome == "checkmate":
                game_obj.winner = current_player
            elif outcome in ["stalemate", "draw_material", "draw"]:
                game_obj.winner = None

        game_obj.save()

        Move.objects.create(
            game=game_obj,
            move_san=move_san,
            move_number=game_obj.moves.count() + 1,
            think_time_seconds=max(0.0, float(elapsed)),
        )

        return {"game": game_obj, "outcome": outcome, "move_applied": True}
