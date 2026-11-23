import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

if sys.platform == "linux":
    import fcntl

    import rxci
    import rxci_aws
    import rxci_board


@unittest.skipUnless(sys.platform == "linux", "Requires Linux flock and /proc/self/fdinfo")
class BoardLeaseTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.registry = rxci.load_registry()
        self.test_case = next(t for t in self.registry["tests"] if t["name"] == "rx72n:sw:tls12:mqtt")

    def board(self):
        board = rxci_board.Board(self.registry, "rx72n")
        board.target = {
            **board.target,
            "hostname": socket.gethostname(),
            "bench_lock": str(self.root / "board.lock"),
            "rfp_lock": str(self.root / "rfp.lock"),
            "owner_file": str(self.root / "owner.json"),
        }
        self.addCleanup(lambda: board._lock.close() if board._lock else None)
        return board

    def test_competing_lock_prevents_cleanup_from_touching_the_board(self):
        board = self.board()
        logs = self.root / "logs"
        with open(board.target["bench_lock"], "a") as benchmark_lock:
            fcntl.flock(benchmark_lock, fcntl.LOCK_EX)
            with mock.patch.object(rxci_board, "Board", return_value=board), \
                 mock.patch.object(board, "park") as park, \
                 mock.patch.object(rxci_aws, "sweep", return_value=[]) as sweep:
                rxci_board.finish_test(self.registry, self.test_case, logs, mock.Mock())
            park.assert_not_called()
            sweep.assert_called_once()
        board._lock.close()
        self.assertTrue(board.try_lock())
        board.check_rx72n_lease()

    def test_recipe_starts_only_after_competing_lock_is_released(self):
        board = self.board()
        logs = self.root / "logs"
        recipe = mock.Mock()
        with open(board.target["bench_lock"], "a") as benchmark_lock:
            fcntl.flock(benchmark_lock, fcntl.LOCK_EX)

            def release_benchmark_lock(_seconds):
                recipe.assert_not_called()
                fcntl.flock(benchmark_lock, fcntl.LOCK_UN)

            with mock.patch.object(rxci_board, "Board", return_value=board), \
                 mock.patch.dict(rxci_board.RECIPES, {("rx72n", "mqtt"): recipe}), \
                 mock.patch.object(rxci_board.signal, "signal"), \
                 mock.patch.object(rxci_board.time, "sleep", side_effect=release_benchmark_lock) as wait:
                self.assertEqual(rxci_board.run_test(self.registry, self.test_case, [], logs), 0)
        wait.assert_called_once()
        recipe.assert_called_once()
        self.assertTrue((logs / "finished").is_file())

    def test_retained_hardware_state_blocks_test_and_after_script(self):
        for filename, message in (("owner.json", "hardware owner"), ("rfp.lock.unsafe.json", "unsafe sentinel")):
            with self.subTest(filename=filename):
                board = self.board()
                record = self.root / filename
                record.write_text(json.dumps({"test": "retained"}), encoding="utf-8")
                try:
                    logs = self.root / filename.replace(".json", "-logs")
                    with mock.patch.object(rxci_board, "Board", return_value=board), \
                         mock.patch.dict(rxci_board.RECIPES, {("rx72n", "mqtt"): mock.Mock()}) as recipes, \
                         mock.patch.object(board, "rest") as rest, \
                         mock.patch.object(board, "park") as park, \
                         mock.patch.object(rxci_board.signal, "signal"), \
                         mock.patch.object(rxci_aws, "sweep", return_value=[]) as sweep:
                        self.assertEqual(rxci_board.run_test(self.registry, self.test_case, [], logs), 1)
                        self.assertIn(message, (logs / "junit.xml").read_text(encoding="utf-8"))
                        self.assertFalse((logs / "finished").exists())
                        recipes[("rx72n", "mqtt")].assert_not_called()
                        rest.assert_not_called()
                        board._lock.close()
                        rxci_board.finish_test(self.registry, self.test_case, logs, mock.Mock())
                    park.assert_not_called()
                    sweep.assert_called_once()
                    self.assertTrue(record.is_file())
                finally:
                    if board._lock:
                        board._lock.close()
                    record.unlink()
