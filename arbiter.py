
import threading
import chess
import functools


class ChessPlayer:
    def enter_turn(self, arbiter):
        pass

    def acknowledge_act(self, arbiter):
        pass

    def report_result(self, arbiter, result):
        pass

    def interrupt(self):
        pass


class Arbiter:
    def __init__(self, players):
        self.game_state = None
        self.players = dict(players)
        self._game_stopped = threading.Event()
        self._lock = threading.Lock()

    def start_game(self):
        self.game_state = chess.GameState(chess.BoardState.with_initial_material())
        self.players[self.game_state.playing_team].enter_turn(self)

    def abort_game(self):
        self._game_stopped.set()
        with self._lock:
            self.players[self.game_state.playing_team].interrupt()

    def select_act(self, act):
        if self._game_stopped.is_set():
            return

        with self._lock:
            if isinstance(act, chess.MoveAct):
                is_legal_act = act.move in self.game_state.compute_legal_moves_for_playing_team()
            elif isinstance(act, chess.ClaimDrawAct):
                is_legal_act = self.game_state.compute_result().may_claim_draw
            else:
                is_legal_act = True

            if is_legal_act:  # check that acts players try to perform are legal.
                player = self.players[self.game_state.playing_team]
                self.game_state = self.game_state.copy_with_act_applied(act)
                player.acknowledge_act(self)  # notify the player we accept his move

            result = self.game_state.compute_result()
            if result.is_finished:
                for player in self.players.values():
                    player.report_result(self, result)
            else:
                # time for current player to make a move - this also happens if a move was invalid
                self.players[self.game_state.playing_team].enter_turn(self)


class AIChessPlayer(ChessPlayer):
    def __init__(self, ai_player):
        self.ai_player = ai_player
        self.ai_waiting_thread = None

    def _enter_turn_in_separate_thread(self, arbiter):
        act = self.ai_player.pick_act(arbiter.game_state)
        arbiter.select_act(act)

    def enter_turn(self, arbiter):
        target = functools.partial(self._enter_turn_in_separate_thread, arbiter)
        self.ai_waiting_thread = threading.Thread(group=None,
                                                  target=target,
                                                  name=None,
                                                  daemon=True)
        self.ai_waiting_thread.start()

    def acknowledge_act(self, arbiter):
        pass

    def report_result(self, arbiter, result):
        pass

    def interrupt(self):
        self.ai_player.abort_computation()
