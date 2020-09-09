
# Chess piece icons downloaded from the web page:
# https://commons.wikimedia.org/wiki/Category:SVG_chess_pieces
# Ideally, the SVG format would be used, but I use PNG files that were used as icons for the corresponding SVG files on
# that page.

import chess
import ai

import functools
import tkinter as tk


class ChessPlayer:
    HUMAN_PLAYER = 0
    RANDOM_MOVE_AI = 1
    PAWNS_AND_QUEENS_AI = 2

    def enter_turn(self, arbiter):
        pass

    def acknowledge_act(self, arbiter):
        pass

    def report_result(self, arbiter, result):
        pass


import threading


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


class ViewOfChessPlayer(ChessPlayer):
    """
    Wraps a ChessPlayer and updates a ChessBoardView to the player's view of the game
    """

    def __init__(self, view, player):
        self.view = view
        self.player = player

    def enter_turn(self, arbiter):
        self.view.game_state = arbiter.game_state
        self.view.set_to_view_of_team(arbiter.game_state.playing_team)
        self.player.enter_turn(arbiter)

    def acknowledge_act(self, arbiter):
        self.view.game_state = arbiter.game_state
        self.player.acknowledge_act(arbiter)

    def report_result(self, arbiter, result):
        self.view.game_state = arbiter.game_state
        self.player.report_result(arbiter, result)


class LocalHumanChessPlayer(ChessPlayer):

    def __init__(self, view):
        self.view = view

    @staticmethod
    def _move_selection_handler(arbiter, move):
        arbiter.select_act(chess.MoveAct(move, False))

    def enter_turn(self, arbiter):
        self.view.allow_move_selection = True
        self.view.move_selection_handler = functools.partial(self._move_selection_handler, arbiter)

    def acknowledge_act(self, arbiter):
        self.view.allow_move_selection = False
        self.view.reset_move_selection()

    def report_result(self, arbiter, result):
        pass


class Arbiter:
    def __init__(self, player_white, player_black):
        self.game_state = None
        self.players = dict(W=player_white, B=player_black)

    def start_game(self):
        self.game_state = chess.GameState(chess.BoardState.with_initial_material())
        self.players[self.game_state.playing_team].enter_turn(self)

    def select_act(self, act):
        if isinstance(act, chess.MoveAct):
            is_legal_act = act.move in self.game_state.compute_legal_moves_for_playing_team()
        elif isinstance(act, chess.ClaimDrawAct):
            is_legal_act = self.game_state.comput_result().may_claim_draw
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
        else:  # time for current player to make a move - this also happens
            self.players[self.game_state.playing_team].enter_turn(self)


class ChessBoardView(tk.Frame):

    def __init__(self, parent):
        super(ChessBoardView, self).__init__(parent)
        # Note that Tkinter PhotoImage's are garbage collected even if they are needed for active widgets, it is
        # mandatory to keep a reference to them for the lifetime of the widget.
        self.empty_image = tk.PhotoImage(file="icons/empty.png")
        self.piece_images_by_team_and_symbol = dict(
            W=dict(
                P=tk.PhotoImage(file="icons/pawn_white.png"),
                R=tk.PhotoImage(file="icons/rook_white.png"),
                N=tk.PhotoImage(file="icons/knight_white.png"),
                B=tk.PhotoImage(file="icons/bishop_white.png"),
                Q=tk.PhotoImage(file="icons/queen_white.png"),
                K=tk.PhotoImage(file="icons/king_white.png")
            ),
            B=dict(
                P=tk.PhotoImage(file="icons/pawn_black.png"),
                R=tk.PhotoImage(file="icons/rook_black.png"),
                N=tk.PhotoImage(file="icons/knight_black.png"),
                B=tk.PhotoImage(file="icons/bishop_black.png"),
                Q=tk.PhotoImage(file="icons/queen_black.png"),
                K=tk.PhotoImage(file="icons/king_black.png")
            )
        )

        self._chess_piece_button_by_ui_grid_pos = dict()
        self._chess_piece_button_by_pos = dict()

        for x in range(0, 8):
            for y in range(0, 8):
                button = tk.Button(self, image=self.empty_image)
                button.grid(column=x, row=y)
                self._chess_piece_button_by_ui_grid_pos[(x, y)] = button

        self.allow_move_selection = False
        self.move_selection_handler = None
        self._game_state = None

        self.set_to_view_of_team('W')
        self._possible_moves_by_to_pos = dict()
        self._reset_square_colors()

    @property
    def game_state(self):
        return self._game_state

    @game_state.setter
    def game_state(self, game_state):
        self._game_state = game_state
        self._update_chess_piece_images()

    def _on_board_square_click(self, x, y):
        if not self.allow_move_selection or self.game_state is None:
            return

        pos = (x, y)

        try:
            moves_to_clicked_position = self._possible_moves_by_to_pos[pos]
            move = moves_to_clicked_position[0]

            if self.move_selection_handler is not None:
                self.move_selection_handler(move)
        except KeyError:
            piece = self.game_state.piece_at(pos)

            if piece is not None and piece.team == self.game_state.playing_team:
                self._show_possible_moves_for_piece(pos)
            else:
                self.reset_move_selection()

    def _set_square_color(self, pos, bg_color):
        button = self._chess_piece_button_by_pos[pos]
        button['background'] = bg_color

    def _reset_square_colors(self):
        for x in range(0, 8):
            for y in range(0, 8):
                self._set_square_color((x, y), "orange" if (x + y) % 2 == 0 else "red")

    def reset_move_selection(self):
        self._possible_moves_by_to_pos.clear()
        self._reset_square_colors()

    def set_to_view_of_team(self, view_of_team):
        for x in range(0, 8):
            for y in range(0, 8):
                self._chess_piece_button_by_pos[(x, 7 - y if view_of_team == 'W' else y)] =\
                    self._chess_piece_button_by_ui_grid_pos[(x, y)]
        self._reset_square_colors()
        self._update_chess_piece_images()

    def _update_chess_piece_images(self):
        for x in range(0, 8):
            for y in range(0, 8):
                pos = (x, y)
                button = self._chess_piece_button_by_pos[pos]
                button['command'] = functools.partial(self._on_board_square_click, x, y)
                piece = self.game_state and self.game_state.piece_at(pos)
                piece_image = self.piece_images_by_team_and_symbol[piece.team][piece.symbol] \
                    if piece is not None else self.empty_image
                button['image'] = piece_image

        self.pack()

    def _show_possible_moves_for_piece(self, pos):
        self.reset_move_selection()

        all_possible_moves = self.game_state.compute_legal_moves_for_playing_team()

        for move in all_possible_moves:
            if move.from_pos == pos:
                try:
                    moves_by_to_pos = self._possible_moves_by_to_pos[move.to_pos]
                    moves_by_to_pos.append(move)
                except KeyError:
                    moves_by_to_pos = [move]
                    self._possible_moves_by_to_pos[move.to_pos] = moves_by_to_pos
                self._set_square_color(move.to_pos, "blue")


class ChessBoardGui(tk.Frame):
    def __init__(self, app):
        super().__init__()

        self.app = app
        self.view = ChessBoardView(self)
        self.view.set_to_view_of_team('W')
        self.view.pack()
        #self.arbiter = Arbiter(ViewOfChessPlayer(self.view, AIChessPlayer(ai.PawnsAndQueensAIPlayer())),
        #                       AIChessPlayer(ai.RandomMoveAIPlayer()))
        self.arbiter = Arbiter(ViewOfChessPlayer(self.view, LocalHumanChessPlayer(self.view)),
                               ViewOfChessPlayer(self.view, LocalHumanChessPlayer(self.view)))
        self.arbiter.start_game()


class ChessApp(tk.Tk):
    def __init__(self):
        super(ChessApp, self).__init__()

        self.gui = ChessBoardGui(self)
        self.gui.pack()


if __name__ == '__main__':
    ChessApp().mainloop()
