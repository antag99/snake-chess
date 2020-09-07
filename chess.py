
from math import copysign


class Move:
    """
    Move type that covers every kind of move in chess except for castling, including en passant.

    Move objects are used both for representing possible actions that a player can take, and recording the actions that
    have been taken by a player. It does, for the sake of convenience, track what pieces were on the relevant squares
    before the move was made. (Although this information is redundant as we keep the whole board state before every
    move).

    Note that to_pos and captured_pos are the same for all capturing fmoves except en passant.
    """
    def __init__(self,
                 from_pos,
                 to_pos,
                 moved_piece,
                 captured_pos=None,
                 captured_piece=None):
        self.from_pos = from_pos
        self.to_pos = to_pos
        self.moved_piece = moved_piece
        self.captured_pos = captured_pos
        self.captured_piece = captured_piece

    def compute_over_board_state(self, board_state):
        new_board_state = board_state
        if self.captured_pos and self.captured_piece:
            new_board_state = new_board_state\
                .copy_with_piece_at(self.captured_pos, None)
        new_board_state = new_board_state\
            .copy_with_piece_at(self.from_pos, None)\
            .copy_with_piece_at(self.to_pos, self.moved_piece)
        return new_board_state


class PawnPromotionMove(Move):
    def __init__(self, from_pos, to_pos, moved_piece,
                 promoted_piece,
                 captured_pos=None,
                 captured_piece=None):
        super().__init__(from_pos, to_pos, moved_piece, captured_pos, captured_piece)
        self.promoted_piece = promoted_piece

    def compute_over_board_state(self, board_state):
        return super(PawnPromotionMove, self)\
            .compute_over_board_state(board_state)\
            .copy_with_piece_at(self.to_pos, self.promoted_piece)


class CastlingMove(Move):
    """
    Castling move, represented by a separate class as the rules for rewriting the board are different than for regular
    moves.
    """
    def __init__(self, from_pos, to_pos, moved_piece, rook_pos, rook_piece):
        super().__init__(from_pos, to_pos, moved_piece)

        self.rook_pos = rook_pos
        self.rook_piece = rook_piece

    @property
    def rook_to_pos(self):
        king_x, _ = self.to_pos
        rook_prev_x, rook_y = self.rook_pos
        new_rook_x = king_x + int(copysign(1, king_x - rook_prev_x))
        return (new_rook_x, rook_y)

    def compute_over_board_state(self, board_state):
        return board_state\
            .copy_with_piece_at(self.from_pos, None)\
            .copy_with_piece_at(self.to_pos, self.moved_piece)\
            .copy_with_piece_at(self.rook_pos, None)\
            .copy_with_piece_at(self.rook_to_pos, self.rook_piece)


class Piece:
    symbol = ' '

    def __init__(self, team):
        self.team = team

    def get_attacked_positions(self, game_state, piece_position):
        """
        Gets the positions this piece attacks. This means that it will check an enemy king if the king is in any of
        these squares.
        """
        return []

    def get_possible_moves(self, game_state, piece_position):
        """
        Gets the moves this piece can make. This is for some pieces moving to one of the attacked positions, but for
        example the pawn can make double-forward-step, move to squares diagonally only if occupied by an enemy piece,
        and be promoted when reaching the end of the board.
        """
        return []


class Pawn(Piece):
    symbol = 'P'

    def __init__(self, team):
        super().__init__(team)

    @property
    def direction(self):
        return dict(W=1, B=-1)[self.team]

    def get_attacked_positions(self, game_state, piece_position):
        piece_x, piece_y = piece_position
        attacked_positions = []
        if piece_y + self.direction in range(0, 7):
            if piece_x - 1 > 0:
                attacked_positions.append((piece_x - 1, piece_y + self.direction))
            if piece_x + 1 < 8:
                attacked_positions.append((piece_x + 1, piece_y + self.direction))
        return attacked_positions

    def get_possible_moves(self, game_state, piece_position):
        possible_moves = []
        piece = game_state.piece_at(piece_position)
        piece_x, piece_y = piece_position

        forward_1_pos = (piece_x, piece_y + self.direction)
        forward_1_is_at_end_of_board = piece_y + self.direction == dict(W=7, B=0)[self.team]
        forward_2_pos = (piece_x, piece_y + self.direction * 2)

        if piece_y + self.direction in range(0, 8):
            for right_left_dir in [-1, 1]:
                attack_pos = (piece_x + right_left_dir, piece_y + self.direction)
                if piece_x + right_left_dir not in range(0, 8):
                    continue

                attacked_piece = game_state.piece_at(attack_pos)
                if attacked_piece is not None and attacked_piece.team != self.team:
                    if forward_1_is_at_end_of_board:
                        for promoted_piece in [Rook(self.team), Knight(self.team), Bishop(self.team), Queen(self.team)]:
                            possible_moves.append(PawnPromotionMove(from_pos=piece_position,
                                                                    to_pos=attack_pos,
                                                                    moved_piece=piece,
                                                                    captured_pos=attack_pos,
                                                                    captured_piece=attacked_piece,
                                                                    promoted_piece=promoted_piece))
                    else:
                        possible_moves.append(Move(from_pos=piece_position, to_pos=attack_pos, moved_piece=piece,
                                                   captured_pos=attack_pos, captured_piece=attacked_piece))

                en_passant_attack_pos = (piece_x + right_left_dir, piece_y)
                en_passant_attacked_piece = game_state.board_state.piece_at(en_passant_attack_pos)
                if en_passant_attacked_piece is not None and en_passant_attacked_piece.symbol == 'P' and \
                        game_state.last_move is not None:
                    if game_state.last_move.to_pos == en_passant_attack_pos and \
                            abs(game_state.last_move.to_pos[1] - game_state.last_move.from_pos[1]) == 2:
                        possible_moves.append(Move(from_pos=piece_position, to_pos=attack_pos, moved_piece=piece,
                                                   captured_pos=en_passant_attack_pos,
                                                   captured_piece=en_passant_attacked_piece))

            if game_state.piece_at(forward_1_pos) is None:
                if forward_1_is_at_end_of_board:
                    for promoted_piece in [Rook(self.team), Knight(self.team), Bishop(self.team), Queen(self.team)]:
                        possible_moves.append(PawnPromotionMove(from_pos=piece_position, to_pos=forward_1_pos,
                                                                moved_piece=piece, promoted_piece=promoted_piece))
                else:
                    possible_moves.append(Move(from_pos=piece_position, to_pos=forward_1_pos, moved_piece=piece))
                    in_initial_position = dict(W=1, B=6)[self.team] == piece_y
                    if in_initial_position and game_state.piece_at(forward_2_pos) is None:
                        possible_moves.append(Move(from_pos=piece_position, to_pos=forward_2_pos, moved_piece=piece))
        return possible_moves


class MoveToAttackedPositionsPiece(Piece):
    def get_possible_moves(self, game_state, piece_position):
        piece = game_state.piece_at(piece_position)
        possible_moves = []
        for attacked_pos in self.get_attacked_positions(game_state, piece_position):
            attacked_piece = game_state.piece_at(attacked_pos)
            if not attacked_piece:
                possible_moves.append(Move(from_pos=piece_position, to_pos=attacked_pos, moved_piece=piece))
            elif attacked_piece.team != self.team:
                possible_moves.append(Move(from_pos=piece_position, to_pos=attacked_pos, moved_piece=piece,
                                           captured_pos=attacked_pos, captured_piece=attacked_piece))
        return possible_moves


class SweepingPiece(MoveToAttackedPositionsPiece):
    """
    Common superclass for rooks, bishops and queens, which all make sweeping moves in a set of directions.
    """
    sweep_directions = []

    def get_attacked_positions(self, game_state, piece_position):
        attacked_positions = []
        (piece_x, piece_y) = piece_position
        for dir_x, dir_y in self.sweep_directions:
            for n in range(1, 8):
                attacked_x, attacked_y = (piece_x + dir_x * n, piece_y + dir_y * n)
                if attacked_x in range(0, 8) and attacked_y in range(0, 8):
                    attacked_piece = game_state.piece_at((attacked_x, attacked_y))
                    attacked_positions.append((attacked_x, attacked_y))
                    if attacked_piece is not None:
                        break
        return attacked_positions


class Rook(SweepingPiece):
    symbol = 'R'
    sweep_directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def __init__(self, team):
        super().__init__(team)


class Knight(MoveToAttackedPositionsPiece):
    symbol = 'N'

    def __init__(self, team):
        super().__init__(team)

    def get_attacked_positions(self, game_state, piece_position):
        piece_x, piece_y = piece_position
        attacked_positions = []

        first_set = [-1, 1]
        second_set = [-2, 2]
        for x_set, y_set in [(first_set, second_set), (second_set, first_set)]:
            for x in x_set:
                if x + piece_x not in range(0, 8):
                    continue
                for y in y_set:
                    if y + piece_y not in range(0, 8):
                        continue
                    attacked_positions.append((piece_x + x, piece_y + y))
        return attacked_positions


class Bishop(SweepingPiece):
    symbol = 'B'
    sweep_directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]

    def __init__(self, team):
        super().__init__(team)


class Queen(SweepingPiece):
    symbol = 'Q'
    sweep_directions = Rook.sweep_directions + Bishop.sweep_directions

    def __init__(self, team):
        super().__init__(team)


class King(MoveToAttackedPositionsPiece):
    symbol = 'K'

    def __init__(self, team):
        super().__init__(team)

    def get_attacked_positions(self, game_state, piece_position):
        piece_x, piece_y = piece_position
        attacked_positions = []
        for x in [-1, 0, 1]:
            if x + piece_x not in range(0, 8):
                continue
            for y in [-1, 0, 1]:
                if x == 0 and y == 0:
                    continue
                if y + piece_y not in range(0, 8):
                    continue
                attacked_positions.append((piece_x + x, piece_y + y))
        return attacked_positions

    def _get_castling_moves(self, game_state, piece_position):
        castling_moves = []
        piece = game_state.piece_at(piece_position)
        piece_x, piece_y = piece_position

        has_king_moved = any(move.moved_piece == piece for move in game_state.historical_moves)

        squares_attacked_by_opponent = game_state.get_squares_attacked_by_team(get_opponent_of(self.team))

        if not has_king_moved and piece_position not in squares_attacked_by_opponent:
            for rook_pos in dict(
                W=[(0, 0), (7, 0)],
                B=[(0, 7), (7, 7)]
            )[self.team]:
                rook_x, rook_y = rook_pos
                rook_piece = game_state.piece_at(rook_pos)
                if rook_piece is None or rook_piece.symbol != 'R' or rook_piece.team != self.team:
                    continue

                has_rook_moved = any(move.to_pos == rook_pos for move in game_state.historical_moves)
                if has_rook_moved:
                    continue

                dir_to_rook = int(copysign(1, rook_x - piece_x))

                is_any_intermediate_square_occupied_or_attacked = False

                for intermediate_x in range(piece_x + dir_to_rook, rook_x, dir_to_rook):
                    if game_state.piece_at((intermediate_x, piece_y)) is not None or \
                            (intermediate_x, piece_y) in squares_attacked_by_opponent:
                        is_any_intermediate_square_occupied_or_attacked = True
                        break

                if is_any_intermediate_square_occupied_or_attacked:
                    continue

                castling_moves.append(CastlingMove(from_pos=piece_position,
                                                   to_pos=(piece_x + dir_to_rook * 2, piece_y),
                                                   moved_piece=piece,
                                                   rook_pos=rook_pos,
                                                   rook_piece=rook_piece))
        return castling_moves

    def get_possible_moves(self, game_state, piece_position):
        regular_moves = super().get_possible_moves(game_state, piece_position)
        castling_moves = self._get_castling_moves(game_state, piece_position)
        return regular_moves + castling_moves


piece_class_by_symbol = dict([(piece_class.symbol, piece_class)
                              for piece_class in [Pawn, Rook, Knight, Bishop, Queen, King]])


def get_opponent_of(team):
    return "BW"["WB".index(team)]


class GameState:

    def __init__(self,
                 board_state,
                 previous_state=None,
                 last_move=None):
        assert board_state is not None
        assert (previous_state is None) == (last_move is None)
        self.board_state = board_state
        self.previous_state = previous_state
        self.last_move = last_move
        self.history_size = 0 if self.previous_state is None else 1 + self.previous_state.history_size
        self.playing_team = 'WB'[self.history_size % 2]

    def piece_at(self, pos):
        return self.board_state.piece_at(pos)

    @property
    def historical_moves(self):
        return ([self.last_move] + self.previous_state.historical_moves) if self.last_move is not None else []

    def get_squares_attacked_by_team(self, team):
        attacked_squares = []
        for pos, piece in self.board_state.positions_and_pieces:
            if piece.team == team:
                attacked_squares += piece.get_attacked_positions(self, pos)
        return attacked_squares

    def _is_king_checked(self, king_team):
        king_pos = None
        for pos, piece in self.board_state.positions_and_pieces:
            if piece.symbol == 'K' and piece.team == king_team:
                king_pos = pos
                break

        attacked_squares = self.get_squares_attacked_by_team(get_opponent_of(king_team))
        return king_pos is None or king_pos in attacked_squares

    def copy_with_move_applied(self, move):
        return GameState(move.compute_over_board_state(self.board_state), self, move)

    def compute_legal_moves_for_playing_team(self):
        possible_moves = []
        for pos, piece in self.board_state.positions_and_pieces:
            if piece.team == self.playing_team:
                for possible_move in piece.get_possible_moves(self, pos):
                    outcome_of_move = self.copy_with_move_applied(possible_move)
                    if not outcome_of_move._is_king_checked(get_opponent_of(outcome_of_move.playing_team)):
                        possible_moves.append((possible_move, outcome_of_move))
        return possible_moves


class BoardState:
    def __init__(self, piece_by_pos):
        self.piece_by_pos = piece_by_pos
        self.positions_and_pieces = [(pos, piece) for pos, piece in self.piece_by_pos.items() if piece is not None]

    @staticmethod
    def empty():
        return BoardState(dict([((x, y), None) for x in range(0, 8) for y in range(0, 8)]))

    @staticmethod
    def with_initial_material():
        board_with_initial_material = BoardState.empty()
        piece_constructor_by_symbol = dict(piece_class_by_symbol)
        piece_constructor_by_symbol[' '] = lambda _: None
        row_number = 0
        for row in ['RNBQKBNR',
                    'PPPPPPPP',
                    '        ',
                    '        ',
                    '        ',
                    '        ',
                    'PPPPPPPP',
                    'RNBKQBNR']:
            column_number = 0
            for piece in row:
                piece_team = 'W' if row_number <= 4 else 'B'
                board_with_initial_material = board_with_initial_material.copy_with_piece_at(
                    (column_number, row_number),
                    piece_constructor_by_symbol[piece](piece_team))
                column_number += 1
            row_number += 1
        return board_with_initial_material

    def copy_with_piece_at(self, pos, piece):
        assert pos in self.piece_by_pos, f"Coordinates are out of range: {pos}"
        new_piece_by_pos = dict(self.piece_by_pos)
        new_piece_by_pos[pos] = piece
        return BoardState(new_piece_by_pos)

    def piece_at(self, pos):
        assert pos in self.piece_by_pos, f"Coordinates are out of range: {pos}"
        return self.piece_by_pos[pos]
