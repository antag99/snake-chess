
from chess import *

from random import Random
from multiprocessing import Pool


class AIPlayer:
    def pick_act(self, game_state):
        pass


class RandomMoveAIPlayer(AIPlayer):
    def __init__(self):
        self.random = Random()

    def pick_act(self, game_state):
        legal_moves = game_state.compute_legal_moves_for_playing_team()
        if len(legal_moves) == 0:  # this should not happen, indicates faulty usage
            return SurrenderAct()
        return MoveAct(legal_moves[self.random.randrange(len(legal_moves))], False)

PIECE_VALUES = dict(P=1, R=5, N=3, B=3, Q=9, K=0)


class MoveScorer:

    def __init__(self, game_state):
        self.game_state = game_state

        self.ai_team = self.game_state.playing_team
        self.enemy_team = get_opponent_of(self.ai_team)
        self.current_attacked_squares = game_state.get_squares_attacked_by_team(self.enemy_team, 'PRNBQ')
        self.current_king_attacked_squares = game_state.get_squares_attacked_by_team(self.enemy_team, 'K')
        self.current_protected_squares = game_state.get_squares_attacked_by_team(self.ai_team)

    def score_move(self, move):
        act = MoveAct(move, False)
        game_state_after = self.game_state.copy_with_act_applied(act)

        if game_state_after.is_king_checked(self.ai_team):
            return None  # illegal move

        result = game_state_after.compute_result()

        if result.is_finished:
            return -1000 if result.outcome == Outcome.DRAW else 1000

        if move.moved_piece.symbol == 'P':
            # Pawn prio list:
            # 1. checkmate
            # 2. pawn promotion, choosing queen and capturing the most valuable enemy piece
            # 3. capturing the most valuable enemy piece
            # 4. moving 2 steps, only one step if not allowed to move further
            if isinstance(move, PawnPromotionMove):
                return 100 + (PIECE_VALUES[move.captured_piece.symbol] if move.captured_piece else 0) + \
                    PIECE_VALUES[move.promoted_piece.symbol]
            if move.captured_piece:
                return 10 + PIECE_VALUES[move.captured_piece.symbol]
            return 1 + abs(move.to_pos[1] - move.from_pos[1])
        elif move.moved_piece.symbol == 'Q':

            # Queen prio list:
            # 1. checkmate
            # 2. pawn promotion, choosing queen and capturing the most valuable enemy piece
            # 3. capturing the most valuable enemy piece
            # 4. moving 2 steps, only one step if not allowed to move further

            under_attack_by_enemy_pieces = game_state_after.get_squares_attacked_by_team(self.enemy_team,
                                                                                         "PRNBQ")
            under_attack_by_enemy_king = game_state_after.get_squares_attacked_by_team(self.enemy_team,
                                                                                       "K")
            protected_by_ai_team = game_state_after.get_squares_attacked_by_team(self.ai_team)

            if move.to_pos in under_attack_by_enemy_pieces:
                return -100

            if move.to_pos in under_attack_by_enemy_king and not move.to_pos in protected_by_ai_team:
                return -100

            is_under_attack = move.from_pos in self.current_attacked_squares or \
                              (move.from_pos in self.current_king_attacked_squares and
                               not move.from_pos in self.current_protected_squares)

            base_score = 100 if is_under_attack else 0

            if move.captured_piece:
                return base_score + PIECE_VALUES[move.captured_piece.symbol]

            return base_score


class PawnsAndQueensAIPlayer(AIPlayer):
    """
    An AI that does not bother to do anything else than advancing pawns and capturing enemy pieces with queens,
    ensuring the queens move if they are under attack, and don't move into a position where they are attacked.

    Moves out of check by random move and claims checkmate when possible. Embarrassingly demanding in terms of CPU
    power.
    """

    def __init__(self):
        self.random = Random()
        self.pool = Pool(8)

    @staticmethod
    def _count_enemy_material(game_state):
        return sum(PIECE_VALUES[piece.symbol]
             for _, piece in game_state.board_state.positions_and_pieces
             if piece.team == game_state.playing_team)

    @staticmethod
    def _score_outcome(game_state):
        result = game_state.compute_result()
        if result.is_finished:
            if result.outcome == Outcome.DRAW:
                return -1000
            else:
                return 1
        return -PawnsAndQueensAIPlayer._count_enemy_material(game_state)

    @staticmethod
    def _score_act(game_state, act):
        return act, PawnsAndQueensAIPlayer._score_outcome(game_state.copy_with_act_applied(act))

    def pick_act(self, game_state):
        ai_team = game_state.playing_team
        enemy_team = get_opponent_of(ai_team)

        all_pieces = list(game_state.board_state.positions_and_pieces)
        my_pieces = [(pos, piece) for pos, piece in all_pieces if piece.team == ai_team]
        self.random.shuffle(my_pieces)

        pawns_and_queens = filter(lambda p: p[1].symbol in 'PQ', my_pieces)

        scorer = MoveScorer(game_state)
        moves = [move for pawn_pos, piece in pawns_and_queens
                      for move in piece.get_possible_moves(game_state, pawn_pos)]

        # score them all (illegal moves get score 'None')
        move_with_score = zip(moves, self.pool.map(scorer.score_move, moves))

        # filter out illegal moves
        move_with_score = list(filter(lambda move_and_score: move_and_score[1] is not None, move_with_score))

        # find the best score
        max_score = max(move_with_score, key=lambda n: n[1], default=(None, None))[1]

        if max_score is not None:
            best_moves = list(filter(lambda move_and_score: move_and_score[1] == max_score, move_with_score))
            self.random.shuffle(best_moves)
            return MoveAct(best_moves[0][0], False)

        if not any(p[1].symbol == 'Q' for p in all_pieces):  # oh no!
            return SurrenderAct()

        possible_acts = [MoveAct(move, False) for move in game_state.compute_legal_moves_for_playing_team()]
        return possible_acts[self.random.randrange(len(possible_acts))]
