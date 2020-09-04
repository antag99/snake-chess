
# Chess piece icons downloaded from the web page:
# https://commons.wikimedia.org/wiki/Category:SVG_chess_pieces
# Ideally, the SVG format would be used, but I use PNG files that were used as icons for the corresponding SVG files on
# that page.

import chess

import functools
import tkinter as tk


class ChessBoardGui(tk.Frame):
    def _chess_piece_clicked(self, x, y):
        pos = (x, y)

        try:
            moves_to_clicked_position = self._possible_moves_by_to_pos[pos]
            move_0, outcome = moves_to_clicked_position[0]
            self._game_state = outcome
            self._reset_square_background_color()
            self._update_chess_piece_images()
            self._possible_moves_by_to_pos = dict()
        except KeyError:
            piece = self._game_state.piece_at(pos)

            if piece is not None and piece.team == self._game_state.get_playing_team():
                self._show_possible_moves_for_piece(pos)
            else:
                self._possible_moves_by_to_pos = dict()
                self._reset_square_background_color()

    def __init__(self):
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

        self._possible_moves_by_to_pos = dict()
        self._chess_piece_button_by_pos = dict()

        for x in range(0, 8):
            for y in range(0, 8):
                button = tk.Button(self, image=self.empty_image)
                button['command'] = functools.partial(self._chess_piece_clicked, x, y)
                button.grid(column=x, row=7 - y)
                self._chess_piece_button_by_pos[(x, y)] = button

        self._game_state = chess.GameState()
        self._reset_square_background_color()
        self._update_chess_piece_images()

    def _set_square_background_color(self, pos, bg_color):
        button = self._chess_piece_button_by_pos[pos]
        button['background'] = bg_color

    def _reset_square_background_color(self):
        for x in range(0, 8):
            for y in range(0, 8):
                self._set_square_background_color((x, y), "orange" if (x + y) % 2 == 0 else "red")

    def _update_chess_piece_images(self):
        for x in range(0, 8):
            for y in range(0, 8):
                pos = (x, y)
                button = self._chess_piece_button_by_pos[pos]
                piece = self._game_state.piece_at(pos)
                piece_image = self.piece_images_by_team_and_symbol[piece.team][piece.symbol] \
                    if piece is not None else self.empty_image
                button['image'] = piece_image

        self.pack()

    def _show_possible_moves_for_piece(self, pos):
        self._reset_square_background_color()
        all_possible_moves = self._game_state.compute_legal_moves_for_playing_team()

        self._possible_moves_by_to_pos = dict()

        for move, outcome in all_possible_moves:
            if move.from_pos == pos:
                try:
                    moves_by_to_pos = self._possible_moves_by_to_pos[move.to_pos]
                    moves_by_to_pos.append(move)
                except KeyError:
                    moves_by_to_pos = [(move, outcome)]
                    self._possible_moves_by_to_pos[move.to_pos] = moves_by_to_pos
                self._set_square_background_color(move.to_pos, "blue")


if __name__ == '__main__':
    app = ChessBoardGui()

    app.mainloop()
