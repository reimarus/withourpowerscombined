import sys
import threading
from collections.abc import Callable
from pathlib import Path

from launcher.deploy import run_setup


class SetupWorker(threading.Thread):
    """
    A worker thread to run the WOPC setup process without freezing the GUI.
    """

    def __init__(
        self,
        on_complete: Callable[[bool], None],
        on_log: Callable[[str], None],
        on_progress: Callable[[str, int, int], None] | None = None,
    ):
        super().__init__(daemon=True)
        self.on_complete = on_complete
        self.on_log = on_log
        self.on_progress = on_progress

    def run(self) -> None:
        """Execute the setup script and report back the result."""
        self.on_log("Starting WOPC deployment in background...")
        try:
            # In frozen exe, init/ is bundled inside _MEIPASS
            if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                init_dir = Path(sys._MEIPASS) / "init"
            else:
                repo_root = Path(__file__).resolve().parent.parent.parent
                init_dir = repo_root / "init"
            run_setup(init_dir, progress_cb=self.on_progress)

            success = True
            self.on_log("Deployment completed successfully!")
            self.on_complete(success)
        except Exception as e:
            self.on_log(f"Critical error during setup: {e}")
            self.on_complete(False)
