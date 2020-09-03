
# Chess piece icons downloaded from the web page:
# https://commons.wikimedia.org/wiki/Category:SVG_chess_pieces
# Ideally, the SVG format would be used, but I use PNG files that were used as icons for the corresponding SVG files on
# that page.

import chess

import functools
import tkinter as tk

class ChessBoardGui(tk.Frame):
    def _chess_piece_clicked(self, x, y):
        print(x,y)

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

        self._flat_chess_piece_buttons_array = [tk.Button(self,
                                                          image=self.empty_image)
                                                for i in range(0, 64)]

        for x in range(0, 8):
            for y in range(0, 8):
                button = self._flat_chess_piece_buttons_array[x + y * 8]
                button['command'] = functools.partial(self._chess_piece_clicked, x, y)
                button['background'] = "orange" if (x + y) % 2 == 0 else "red"
                button.grid(column=x, row=7 - y)

        self._game_state = chess.GameState()
        self._update_chess_piece_images()

    def _update_chess_piece_images(self):
        for x in range(0, 8):
            for y in range(0, 8):
                button = self._flat_chess_piece_buttons_array[x + y * 8]
                piece = self._game_state.piece_at((x, y))
                piece_image = self.piece_images_by_team_and_symbol[piece.team][piece.symbol] \
                    if piece is not None else self.empty_image
                button['image'] = piece_image

        self.pack()


if __name__ == '__main__':
    app = ChessBoardGui()

    app.mainloop()
