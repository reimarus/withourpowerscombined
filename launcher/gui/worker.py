import threading
from collections.abc import Callable

from launcher.deploy import run_setup


class SetupWorker(threading.Thread):
    """
    A worker thread to run the WOPC setup process without freezing the GUI.
    """

    def __init__(self, on_complete: Callable[[bool], None], on_log: Callable[[str], None]):
        super().__init__(daemon=True)
        self.on_complete = on_complete
        self.on_log = on_log

    def run(self) -> None:
        """Execute the setup script and report back the result."""
        self.on_log("Starting WOPC deployment in background...")
        try:
            # We override the direct console print/logging by wrapping it or just running
            # For now, run_setup() logs to the standard python logger. We will catch
            # its success/failure status.
            success = run_setup() == 0
            if success:
                self.on_log("Deployment completed successfully!")
            else:
                self.on_log("Deployment failed. Check WOPC.log for details.")
            self.on_complete(success)
        except Exception as e:
            self.on_log(f"Critical error during setup: {e}")
            self.on_complete(False)
