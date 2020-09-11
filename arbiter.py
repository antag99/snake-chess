
import threading
import chess
import functools


class ChessPlayer:
    """
    Represents a player in the game, human or AI. Interfaces to the mechanism by which a player chooses its moves.
    """

    def on_turn_to_act(self, arbiter):
        """
        Called when this player should act. When the player has decided what move to make, it should invoke
        arbiter.pick_act.

        :param arbiter: the arbiter of the game
        """
        pass

    def cancel_turn_to_act(self, arbiter):
        """
        Called to withdraw the opportunity of the player to act. Invoked if the game is aborted, could also come to use
        if turn timing is implemented.

        :param arbiter: the arbiter of the game
        """
        pass


class GameWatcher:
    """
    Watcher that is notified of game state updates. Used to update the display of the game and determine when a game
    has finished.
    """

    def on_game_state_changed(self, arbiter):
        """
        Called to notify the game watcher of the current game state. Called at the beginning of the game and after
        every move, and thereby also when the game is finished.

        :param arbiter: the arbiter of the game
        """
        pass


class Arbiter:
    def __init__(self, players):
        self.game_state = None
        self.players = dict(players)
        self.watchers = []
        self._game_stopped = threading.Event()
        self._lock = threading.Lock()

    def _notify_watchers(self):
        for watcher in self.watchers:
            watcher.on_game_state_changed(self)

    def start_game(self):
        self.game_state = chess.GameState(chess.BoardState.with_initial_material())
        self._notify_watchers()
        self.players[self.game_state.playing_team].on_turn_to_act(self)

    def abort_game(self):
        self._game_stopped.set()
        with self._lock:
            self.players[self.game_state.playing_team].cancel_turn_to_act(self)

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
                self.game_state = self.game_state.copy_with_act_applied(act)
                self._notify_watchers()

            if not is_legal_act or not self.game_state.compute_result().is_finished:
                self.players[self.game_state.playing_team].on_turn_to_act(self)


class AIChessPlayer(ChessPlayer):
    def __init__(self, ai_player):
        self.ai_player = ai_player
        self.ai_waiting_thread = None

    def _pick_act_in_separate_thread(self, arbiter):
        # We pick the act in a separate thread, it will spend a lot of time waiting for separate processes to finish
        # the computation. This way the GUI can remain responsive while the AI is thinking.
        act = self.ai_player.pick_act(arbiter.game_state)
        arbiter.select_act(act)

    def on_turn_to_act(self, arbiter):
        target = functools.partial(self._pick_act_in_separate_thread, arbiter)
        self.ai_waiting_thread = threading.Thread(group=None,
                                                  target=target,
                                                  name=None,
                                                  daemon=True)
        self.ai_waiting_thread.start()

    def cancel_turn_to_act(self, arbiter):
        self.ai_player.abort_computation()
