
# Chess piece icons downloaded from the web page:
# https://commons.wikimedia.org/wiki/Category:SVG_chess_pieces
# Ideally, the SVG format would be used, but I use PNG files that were used as icons for the corresponding SVG files on
# that page.

import chess
import ai

import functools
import tkinter as tk
import tkinter.font


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

    def interrupt(self):
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

    def interrupt(self):
        self.ai_player.abort_computation()


class ViewOfChessPlayer(ChessPlayer):
    """
    Wraps a ChessPlayer and updates a ChessBoardView to the player's view of the game
    """

    def __init__(self, gui, player):
        self.gui = gui
        self.player = player

    def enter_turn(self, arbiter):
        self.gui.view.game_state = arbiter.game_state
        self.gui.view.set_to_view_of_team(arbiter.game_state.playing_team)
        self.gui.game_status_frame.update_to_game_state(arbiter.game_state)
        self.player.enter_turn(arbiter)

    def acknowledge_act(self, arbiter):
        self.gui.view.game_state = arbiter.game_state
        self.gui.game_status_frame.update_to_game_state(arbiter.game_state)
        self.player.acknowledge_act(arbiter)

    def report_result(self, arbiter, result):
        self.gui.view.game_state = arbiter.game_state
        self.gui.game_status_frame.update_to_game_state(arbiter.game_state)
        self.player.report_result(arbiter, result)


class LocalHumanChessPlayer(ChessPlayer):

    def __init__(self, gui):
        self.gui = gui
        self.offer_draw = False

    def _move_selection_handler(self, arbiter, move):
        arbiter.select_act(chess.MoveAct(move, self.offer_draw))

    def _set_offer_draw_handler(self, offer_draw):
        self.offer_draw = offer_draw

    def _claim_draw_handler(self, arbiter):
        arbiter.select_act(chess.ClaimDrawAct())

    def _surrender_handler(self, arbiter):
        arbiter.select_act(chess.SurrenderAct())

    def enter_turn(self, arbiter):
        self.gui.view.allow_move_selection = True
        self.gui.view.move_selection_handler = functools.partial(self._move_selection_handler, arbiter)

        self.offer_draw = False
        self.gui.set_offer_draw_handler = self._set_offer_draw_handler
        self.gui.claim_draw_handler = functools.partial(self._claim_draw_handler, arbiter)
        self.gui.surrender_handler = functools.partial(self._surrender_handler, arbiter)
        self.gui.game_status_frame.set_act_buttons_active(True)

    def acknowledge_act(self, arbiter):
        self.gui.view.allow_move_selection = False
        self.gui.view.reset_move_selection()
        self.gui.clear_handlers()
        self.gui.game_status_frame.set_act_buttons_active(False)

    def report_result(self, arbiter, result):
        pass

    def interrupt(self):
        self.gui.view.reset_move_selection()


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


class ChessBoardView(tk.Frame):

    def __init__(self, parent, gui):
        super(ChessBoardView, self).__init__(parent)
        self.gui = gui

        self._chess_piece_button_by_ui_grid_pos = dict()
        self._chess_piece_button_by_pos = dict()

        for x in range(0, 8):
            for y in range(0, 8):
                button = tk.Button(self, image=self.gui.empty_image, borderwidth=0)
                button.grid(column=x, row=y, padx=0, pady=0)
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
        button['activebackground'] = bg_color

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
                piece_image = self.gui.piece_images_by_team_and_symbol[piece.team][piece.symbol] \
                    if piece is not None else self.gui.empty_image
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
    class GameStartButtonsFrame(tk.Frame):
        def __init__(self, parent, gui):
            super().__init__(parent, gui)

            players = [
                ("Human", LocalHumanChessPlayer(gui)),
                ("Random moves", AIChessPlayer(ai.RandomMoveAIPlayer())),
                ("Stupid AI", AIChessPlayer(ai.PawnsAndQueensAIPlayer())),
            ]

            player_selection = dict(W=players[0][1], B=players[0][1])

            for team in 'WB':
                var = tk.IntVar(self, 0, team + "_player")

                def player_selection_change(team, var):
                    player_selection[team] = players[var.get()][1]

                tk.Label(self,
                         text=dict(W='White', B='Black')[team],
                         font=tkinter.font.Font(family='Arial', size=12, weight=tkinter.font.BOLD)).pack(anchor='w', padx=6)

                buttons = [tk.Radiobutton(self,
                                          text=players[i][0],
                                          variable=var,
                                          value=i) for i in range(0, 3)]
                for button in buttons:
                    button['command'] = functools.partial(player_selection_change, team, var)
                    button.pack(anchor='w')

            def start_game():
                chess_players = dict(player_selection)
                any_human_player = False

                # Human players get the view changed to their perspective when they enter a turn.
                for team in 'WB':
                    if isinstance(chess_players[team], LocalHumanChessPlayer):
                        any_human_player = True
                        chess_players[team] = ViewOfChessPlayer(gui, chess_players[team])

                # If there is no human player, show the view from the white player's perspective
                if not any_human_player:
                    chess_players['W'] = ViewOfChessPlayer(gui, chess_players['W'])

                gui.start_game(chess_players)

            start_game_button = tk.Button(self,
                                          text='Start game!',
                                          command=start_game)
            start_game_button.pack()

    class GameActButtonsFrame(tk.Frame):
        def __init__(self, parent, gui, game_state):
            super().__init__(parent)

            self.gui = gui

            self.offer_draw_var = tk.IntVar()
            self.offer_draw = tk.Checkbutton(self, text="Offer Draw", variable=self.offer_draw_var,
                                             command=lambda: self.gui.set_offer_draw_handler(
                                                 self.offer_draw_var.get() and True or False))

            self.surrender_button = tk.Button(self, text="Surrender", command=self.gui.surrender_handler)
            self.surrender_button.pack(side='right')
            self.claim_draw_button = tk.Button(self, text="Claim draw", command=self.gui.claim_draw_handler)

            result = game_state.compute_result()
            print("may claim draw=", result.may_claim_draw)
            if result.may_claim_draw:
                self.claim_draw_button['text'] = "Claim draw by " + result.may_claim_draw_by_rule.describe(game_state)
                self.claim_draw_button.pack(side='right')
            else:
                self.offer_draw.pack(side='right')

    class GameStatusFrame(tk.Frame):
        def __init__(self, parent, gui):
            super().__init__(parent)

            self.gui = gui
            self._abort_game_button = tk.Button(self,
                                                text='Abort game',
                                                command=self.gui.abort_game)
            self._abort_game_button.pack(side='left', anchor='w', padx=25, pady=10)

            self.status_label = tk.Label(self, text='', font=tkinter.font.Font(family='Arial', size=12,
                                                                               weight=tkinter.font.BOLD))
            self.status_label.pack(side='right', anchor='w', padx=5)

            self.act_buttons = None
            self.game_state = None

            # self.material_display = [None, None]
            # for i in range(0, 2):
            #     material_frame = tk.Frame(self)
            #     material_frame.pack()
            #     self.material_display[i] = material_frame

            # self._scaled_image_cache = dict()
            # for t in 'WB':
            #     scaled = dict()
            #     for symbol in self.gui.piece_images_by_team_and_symbol[t]:
            #         original_image = self.gui.piece_images_by_team_and_symbol[t][symbol]
            #         scaled[symbol] = original_image.subsample(4)
            #     self._scaled_image_cache[t] = scaled

        def set_act_buttons_active(self, act_buttons_active):
            if (self.act_buttons is None) != act_buttons_active:
                return

            if not act_buttons_active:
                self.act_buttons.destroy()
                self.act_buttons = None
            else:
                self.act_buttons = self.gui.GameActButtonsFrame(self, self.gui, self.game_state)
                self.act_buttons.pack(side='right')

        def update_to_game_state(self, game_state):
            self.game_state = game_state

            result = game_state.compute_result()

            if result.is_finished:
                status_text = result.outcome.describe() + " by " + result.ended_by_rule.describe(game_state)
                self._abort_game_button['text'] = "Close game"
            else:
                status_text = dict(W="White", B="Black")[game_state.playing_team] + " moves"
            self.status_label['text'] = status_text

            # for i, team in [(0, 'W'), (1, 'B')]:
            #     material = [piece.symbol for pos, piece in game_state.board_state.positions_and_pieces if piece.team == team]
            #     material.sort(key='PRNBQK'.index)
            #
            #     self.material_display[i].destroy()
            #     self.material_display[i] = tk.Frame(self)
            #     for symbol in material:
            #         if symbol != 'K':
            #             image = self._scaled_image_cache[team][symbol]
            #             img = tk.Label(self.material_display[i], image=image)
            #             img.pack(side='right', anchor='w')
            #     self.material_display[i].pack()

    def __init__(self, app):
        super().__init__()
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

        self.app = app
        self.view_and_status_frame = tk.Frame(self)
        self.view_and_status_frame.pack(side='left')
        self.view = ChessBoardView(self.view_and_status_frame, self)
        self.view.set_to_view_of_team('W')
        self.view.pack(expand=True, side='top', anchor='ne', padx=20, pady=20)
        self.arbiter = None
        self.game_status_frame = None
        self._game_starts_buttons_frame = None
        self._abort_game_button = None
        self._open_game_configuration()

        self.set_offer_draw_handler = None
        self.surrender_handler = None
        self.claim_draw_handler = None
        self.clear_handlers()

    def clear_handlers(self):
        self.set_offer_draw_handler = lambda _: None
        self.surrender_handler = lambda _: None
        self.claim_draw_handler = lambda _: None

    def _open_game_configuration(self):
        self._game_starts_buttons_frame = self.GameStartButtonsFrame(self, self)
        self._game_starts_buttons_frame.pack(side='right', anchor='w')

    def abort_game(self):
        self.arbiter.abort_game()
        self.arbiter = None
        self.game_status_frame.destroy()
        self.game_status_frame = None
        self._open_game_configuration()

    def start_game(self, chess_players):
        self._game_starts_buttons_frame.destroy()
        self._game_starts_buttons_frame = None
        self.game_status_frame = self.GameStatusFrame(self.view_and_status_frame, self)
        self.game_status_frame.pack(side='bottom', anchor='w')
        self.arbiter = Arbiter(chess_players)
        self.arbiter.start_game()


class ChessApp(tk.Tk):
    def __init__(self):
        super(ChessApp, self).__init__()

        self.gui = ChessBoardGui(self)
        self.gui.pack()


if __name__ == '__main__':
    ChessApp().mainloop()
