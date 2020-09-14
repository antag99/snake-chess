
# Chess piece icons downloaded from the web page:
# https://commons.wikimedia.org/wiki/Category:SVG_chess_pieces
# Ideally, the SVG format would be used, but I use PNG files that were used as icons for the corresponding SVG files on
# that page.

import chess
import ai

import functools
import tkinter as tk
import tkinter.font
import threading
import collections
import time


import arbiter


class GUIGameWatcher(arbiter.GameWatcher):
    def __init__(self, gui, players_to_follow) -> None:
        self.gui = gui
        self.players_to_follow = players_to_follow
        self.last_update_timestamp = None
        self.min_time_since_last_update = 0.8

    def on_game_state_changed(self, arbiter):
        game_state = arbiter.game_state

        def ui_task():
            if game_state.playing_team in self.players_to_follow:
                self.gui.view.set_to_view_of_team(game_state.playing_team)
            else:
                self.gui.view.set_to_view_of_team(self.players_to_follow[0])

            self.gui.view.game_state = game_state

            if self.gui.game_status_frame:  # if game has not been canceled
                self.gui.game_status_frame.update_to_game_state(game_state)

        self.gui.run_on_ui_thread(ui_task)

        # wait on this thread to allow the GUI thread to catch up (GUI updates are quite slow.)
        timestamp = time.monotonic()
        time_since_last_update = self.last_update_timestamp and (timestamp - self.last_update_timestamp) or self.min_time_since_last_update
        self.last_update_timestamp = timestamp
        time.sleep(max(0, self.min_time_since_last_update - time_since_last_update))

        # this ensures we do not overload the UI thread, which will end up never returning until game is finished.
        with self.gui.ui_thread_done:
            self.gui.ui_thread_done.wait()


class GUIHumanChessPlayer(arbiter.ChessPlayer):
    def __init__(self, gui):
        self.gui = gui
        self.offer_draw = False

    def _move_selection_handler(self, arbiter, move):
        self.cancel_turn_to_act(arbiter)
        arbiter.select_act(chess.MoveAct(move, self.offer_draw))

    def _set_offer_draw_handler(self, offer_draw):
        self.offer_draw = offer_draw

    def _claim_draw_handler(self, arbiter):
        arbiter.select_act(chess.ClaimDrawAct())
        self.cancel_turn_to_act(arbiter)

    def _surrender_handler(self, arbiter):
        arbiter.select_act(chess.SurrenderAct())
        self.cancel_turn_to_act(arbiter)

    def on_turn_to_act(self, arbiter):
        def ui_task():
            self.gui.view.allow_move_selection = True
            self.gui.view.move_selection_handler = functools.partial(self._move_selection_handler, arbiter)

            self.offer_draw = False
            self.gui.set_offer_draw_handler = self._set_offer_draw_handler
            self.gui.claim_draw_handler = functools.partial(self._claim_draw_handler, arbiter)
            self.gui.surrender_handler = functools.partial(self._surrender_handler, arbiter)
            self.gui.game_status_frame.set_act_buttons_active(True)
        self.gui.run_on_ui_thread(ui_task)

    def cancel_turn_to_act(self, arbiter):
        def ui_task():
            self.gui.view.allow_move_selection = False
            self.gui.view.reset_move_selection()
            self.gui.clear_handlers()
            self.gui.game_status_frame.set_act_buttons_active(False)
        self.gui.run_on_ui_thread(ui_task)


class ChessBoardView(tk.Frame):
    class Square:
        def __init__(self, button):
            self.button = button
            self.bg_color = None
            self.piece_team_and_symbol = None

    def __init__(self, parent, gui):
        super(ChessBoardView, self).__init__(parent)
        self.gui = gui

        self._chess_square_by_ui_grid_pos = dict()
        self._chess_square_by_pos = dict()

        for x in range(0, 8):
            for y in range(0, 8):
                button = tk.Button(self, image=self.gui.empty_image, borderwidth=0)
                button.grid(column=x, row=y, padx=0, pady=0)
                self._chess_square_by_ui_grid_pos[(x, y)] = self.Square(button=button)

        self.allow_move_selection = False
        self.move_selection_handler = None
        self._game_state = None
        self._view_of_team = None

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

    class PawnPromotionDialog(tk.Toplevel):
        # https://effbot.org/tkinterbook/tkinter-dialog-windows.htm

        def __init__(self, parent, gui, moves_to_choose):
            super().__init__(parent)

            self.gui = gui
            self.title("Choose pawn promotion")

            self.transient(parent)
            self.parent = parent
            self.grab_set()
            self.protocol("WM_DELETE_WINDOW", self.cancel)

            self.moves_to_choose = moves_to_choose

            for i in range(0, len(moves_to_choose)):
                move = moves_to_choose[i]
                button = tk.Button(self, image=gui.piece_images_by_team_and_symbol
                [move.promoted_piece.team][move.promoted_piece.symbol], command=functools.partial(self.choose, move))
                button.pack(side='right')

            tk.Button(self, text='Cancel', command=self.cancel).pack(side='right')

        def choose(self, move):
            if self.parent.move_selection_handler is not None:
                self.parent.move_selection_handler(move)
            self.cancel()

        def cancel(self):
            self.parent.focus_set()
            self.destroy()

    def _on_board_square_click(self, x, y):
        if not self.allow_move_selection or self.game_state is None:
            return

        pos = (x, y)

        try:
            moves_to_clicked_position = self._possible_moves_by_to_pos[pos]

            if len(moves_to_clicked_position) > 1:
                self.PawnPromotionDialog(self, self.gui, moves_to_clicked_position)
            else:
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
        square = self._chess_square_by_pos[pos]
        if square.bg_color != bg_color:
            square.button['background'] = bg_color
            square.button['activebackground'] = bg_color

    def _reset_square_colors(self):
        for x in range(0, 8):
            for y in range(0, 8):
                self._set_square_color((x, y), "orange" if (x + y) % 2 == 0 else "red")

    def reset_move_selection(self):
        self._possible_moves_by_to_pos.clear()
        self._reset_square_colors()

    def set_to_view_of_team(self, view_of_team):
        if self._view_of_team == view_of_team:
            return
        self._view_of_team = view_of_team

        for x in range(0, 8):
            for y in range(0, 8):
                square = self._chess_square_by_ui_grid_pos[(x, y)]
                board_pos = (7 - x if view_of_team == 'B' else x, 7 - y if view_of_team == 'W' else y)
                self._chess_square_by_pos[board_pos] = square
                square.button['command'] = functools.partial(self._on_board_square_click, board_pos[0], board_pos[1])
        self._reset_square_colors()
        self._update_chess_piece_images()

    def _update_chess_piece_images(self):
        for x in range(0, 8):
            for y in range(0, 8):
                pos = (x, y)
                square = self._chess_square_by_pos[pos]
                piece = self.game_state and self.game_state.piece_at(pos)
                team_and_symbol = piece and piece.team + piece.symbol

                if square.piece_team_and_symbol != team_and_symbol:
                    square.piece_team_and_symbol = team_and_symbol
                    piece_image = self.gui.piece_images_by_team_and_symbol[piece.team][piece.symbol] \
                        if piece is not None else self.gui.empty_image
                    square.button['image'] = piece_image

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
                ("Human", lambda: GUIHumanChessPlayer(gui)),
                ("Random moves", lambda: arbiter.AIChessPlayer(ai.RandomMoveAIPlayer())),
                ("Stupid AI", lambda: arbiter.AIChessPlayer(ai.PawnsAndQueensAIPlayer())),
            ]

            player_selection = dict(W=players[0][1](), B=players[0][1]())

            for team in 'WB':
                var = tk.IntVar(self, 0, team + "_player")

                def player_selection_change(team, var):
                    player_selection[team] = players[var.get()][1]()

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

            start_game_button = tk.Button(self,
                                          text='Start game!',
                                          command=lambda: gui.start_game(dict(player_selection)))
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
        self.ui_tasks = collections.deque()
        self.ui_thread_done = threading.Condition()
        self._run_tkinter_tasks()

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
        self.arbiter = arbiter.Arbiter(chess_players)
        players_to_follow = filter(lambda t: isinstance(chess_players[t], GUIHumanChessPlayer), "WB")
        self.arbiter.watchers.append(GUIGameWatcher(self, list(players_to_follow) or "W"))
        self.run_on_new_thread(self.arbiter.start_game)

    def run_on_new_thread(self, task):
        thread = threading.Thread(group=None, name=None, target=task)
        thread.start()

    def run_on_ui_thread(self, task):
        self.ui_tasks.append(task)

    def _run_tkinter_tasks(self):
        while len(self.ui_tasks) > 0:
            self.ui_tasks.popleft()()

        with self.ui_thread_done:
            self.ui_thread_done.notify()

        self.after(1, self._run_tkinter_tasks)


class ChessApp(tk.Tk):
    def __init__(self):
        super(ChessApp, self).__init__()

        self.title("Chess game")

        self.gui = ChessBoardGui(self)
        self.gui.pack()


if __name__ == '__main__':
    ChessApp().mainloop()
