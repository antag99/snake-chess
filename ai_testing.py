
import chess
import ai
import arbiter

import threading
import time


def run_game(i, timeout=300):
    """
    Runs a game between the stupid AI and random moves, returns the result seen from the stupid AI's
    perspective; victory, draw, defeat or timeout.
    """
    print("running game", i, "with a timeout of", timeout)

    players = [
        arbiter.AIChessPlayer(ai_player=ai.PawnsAndQueensAIPlayer()),
        arbiter.AIChessPlayer(ai_player=ai.RandomMoveAIPlayer()),
    ]

    finished = threading.Event()

    def state_changed(a):
        # if a.game_state.playing_team == "WB"[i % 2]:
        #     print(a.game_state.board_state)
        result = a.game_state.compute_result()
        if result.is_finished:
            finished.set()

    game_watcher = arbiter.GameWatcher()
    game_watcher.on_game_state_changed = state_changed

    a = arbiter.Arbiter(dict(
        W=players[i % 2],
        B=players[(i + 1) % 2]
    ))
    a.watchers.append(game_watcher)
    a.start_game()


    begin_time = time.monotonic()

    while not finished.is_set() and time.monotonic() - begin_time < timeout:
        time.sleep(1)

    if not finished.is_set():
        print("Not finished after", timeout, "seconds, aborting game")
        a.abort_game()
        return "timeout"

    result = a.game_state.compute_result()

    if result.outcome == chess.Outcome.DRAW:
        return "draw"

    if [chess.Outcome.WHITE_WINS, chess.Outcome.BLACK_WINS][i % 2] == result.outcome:
        return "victory"
    else:
        return "defeat"


if __name__ == "__main__":
    from collections import Counter
    num_games = 10
    outcomes = Counter(timeout=0,draw=0,victory=0,defeat=0)

    print("running", num_games, "games...")
    for i in range(0, num_games):
        outcome = run_game(i)
        print(outcome)
        outcomes.update(outcome)

    print("done; outcomes:")
    for outcome in 'victory draw timeout defeat'.split():
        print(outcome + ": " + str(outcomes[outcome]) + "times")
