
import sys
import chess
import ai
import arbiter
import time
import threading


class CLIHumanPlayer(arbiter.ChessPlayer):

    def __init__(self, cli):
        self.cli = cli

    def on_turn_to_act(self, arbiter):
        self.cli.time_to_play.set()

    def cancel_turn_to_act(self, arbiter):
        pass


class CLIGameStateWatcher(arbiter.GameWatcher):

    def __init__(self):
        self.game_finished = threading.Event()

    def on_game_state_changed(self, arbiter):
        game_state = arbiter.game_state
        sys.stdout.write('-' * 15 + "\n" + game_state.board_state.to_string(game_state.playing_team))
        result = game_state.compute_result()
        if result.is_finished:
            sys.stdout.write(result.outcome.describe() + " by " + result.ended_by_rule.describe(game_state) + "\n")
            self.game_finished.set()
        else:
            sys.stdout.write(dict(W="White", B="Black")[game_state.playing_team] + " moves.\n")
            if result.may_claim_draw:
                sys.stdout.write("May claim draw by " + result.may_claim_draw_by_rule.describe(game_state) + "\n")


class CommandLineInterface:
    def __init__(self):
        self.time_to_play = threading.Event()

    def _parse_move_notation(self, playing_team, notation):
        """
        Parses the given move notation

        :param notation: the notation
        :return: symbol of piece to move; predicate for from_pos, to_pos, piece to promote to
                 or None if notation is invalid.
        """
        def consume(chars):
            nonlocal notation

            if len(notation) > 0 and notation[0] in chars:
                result = notation[0]
                notation = notation[1:]
                return result
            else:
                return None

        if notation == "O-O" or notation == "O-O-O":  # kingside or queenside castling
            king_pos = dict(W=(4, 0), B=(4, 7))[playing_team]
            kingside_dir = dict(W=1, B=-1)[playing_team]
            to_pos = (king_pos[0] + kingside_dir * (-2 if notation == "O-O-O" else 2), king_pos[1])
            return 'K', lambda p: king_pos == p, to_pos, None

        piece_symbol = consume(chess.piece_class_by_symbol) or "P"

        letters = "abcdefgh"
        digits = "12345678"

        col_0 = consume(letters)
        row_0 = consume(digits)

        col_1 = consume(letters)
        row_1 = consume(digits)

        if consume("="):
            promoted_to = consume(chess.piece_class_by_symbol)
            if not promoted_to:
                return None
        else:
            promoted_to = None

        if not col_1:
            if row_1:
                return None
            if not col_0 and col_1:
                return None
            if len(notation) > 0:
                return None
            to_pos = (letters.index(col_0), digits.index(row_0))
            return piece_symbol, lambda _: True, to_pos, promoted_to
        if not row_1:
            return None

        if len(notation) > 0:
            return None

        to_pos = (col_1 and letters.index(col_1), row_1 and digits.index(row_1))

        return piece_symbol, lambda from_pos: (not col_0 or from_pos[0] == letters.index(col_0)) and \
                                              (not row_0 or from_pos[1] == digits.index(row_0)), to_pos, promoted_to

    def on_player_enter_turn(self, arbiter):
        offer_draw = False

        while True:
            sys.stdout.write(dict(W="White", B="Black")[arbiter.game_state.playing_team] + "> ")

            move = next(sys.stdin).strip()
            if "claim draw" == move:
                arbiter.select_act(chess.ClaimDrawAct())
                break
            elif "surrender" == move:
                arbiter.select_act(chess.SurrenderAct())
                break
            elif "offer draw" == move:
                offer_draw = not offer_draw
                if offer_draw:
                    sys.stdout.write("Offering draw to opponent after making move.\n")
                else:
                    sys.stdout.write("Not offering draw to opponent after making move.\n")
                continue
            elif len(move) > 0:
                move_notation = self._parse_move_notation(arbiter.game_state.playing_team, move)
                if not move_notation:
                    sys.stdout.write("Invalid notation. Use PGN without capture, check or checkmate notation.\n")
                else:
                    symbol, from_pos_predicate, to_pos, promoted_to = move_notation

                    def is_matching_move(move):
                        return all([
                            move.moved_piece.symbol == symbol,
                            from_pos_predicate(move.from_pos),
                            move.to_pos == to_pos,
                            promoted_to is None or isinstance(move, chess.PawnPromotionMove),
                            not isinstance(move, chess.PawnPromotionMove) or \
                            (promoted_to or "Q") == move.promoted_piece.symbol
                        ])

                    moves = list(filter(is_matching_move, arbiter.game_state.compute_legal_moves_for_playing_team()))

                    if len(moves) == 0:
                        sys.stdout.write("Impossible move.\n")
                    elif len(moves) > 1:
                        sys.stdout.write("Ambiguous move. Specify the position of the piece to move explicitly.\n")
                    else:
                        arbiter.select_act(chess.MoveAct(moves[0], offer_draw))
                        break

    def setup_game(self):
        player_by_id = dict(
            human=lambda: CLIHumanPlayer(self),
            random_moves=lambda: arbiter.AIChessPlayer(ai.RandomMoveAIPlayer()),
            stupid_ai=lambda: arbiter.AIChessPlayer(ai.PawnsAndQueensAIPlayer())
        )

        players = dict(
            W=None,
            B=None
        )

        any_human = False

        def choose_player(name, team):
            nonlocal any_human
            while True:
                sys.stdout.write(name + "? ")
                player_id = next(sys.stdin).strip()
                if player_id in player_by_id:
                    player = player_by_id[player_id]()
                    if isinstance(player, CLIHumanPlayer):
                        any_human = True
                    players[team] = player
                    break
                else:
                    sys.stdout.write("Invalid player, choose one of: human, random_moves, stupid_ai.\n")

        choose_player("White", "W")
        choose_player("Black", "B")

        if any_human:
            sys.stdout.write("Starting game. When it's your turn to make a move, you may type moves in PGN or "
                             "surrender, offer draw, or claim draw when applicable.\n")

        a = arbiter.Arbiter(players)
        watcher = CLIGameStateWatcher()
        a.watchers.append(watcher)
        a.start_game()

        while True:
            if self.time_to_play.is_set():
                self.time_to_play.clear()
                self.on_player_enter_turn(a)
            elif not watcher.game_finished.is_set():
                time.sleep(0.25)
            else:
                break

    def main(self):

        sys.stdout.write("""
Welcome!

Start by setting up players. Each player can be human, random_moves or stupid_ai.
""".lstrip())

        self.setup_game()


if __name__ == '__main__':
    CommandLineInterface().main()