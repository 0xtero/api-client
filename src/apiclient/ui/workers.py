from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

from apiclient.http.executor import HttpExecutor
from apiclient.models.request import HttpRequest, HttpResponse


class HttpWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, request: HttpRequest) -> None:
        super().__init__()
        self._request = request
        self._executor = HttpExecutor()

    def run(self) -> None:
        try:
            response = self._executor.send(self._request)
            self.finished.emit(response)
        except Exception as exc:  # noqa: BLE001 — surface unexpected errors to UI
            self.failed.emit(str(exc))


class HttpRequestRunner:
    """Run HTTP requests off the UI thread."""

    def __init__(self) -> None:
        self._thread: QThread | None = None
        self._worker: HttpWorker | None = None

    def start(
        self,
        request: HttpRequest,
        on_finished: Callable[[HttpResponse], None],
        on_failed: Callable[[str], None],
    ) -> None:
        self.cancel()

        thread = QThread()
        worker = HttpWorker(request)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(on_finished)
        worker.finished.connect(thread.quit)
        worker.failed.connect(on_failed)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        thread.start()

    def cancel(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        self._thread = None
        self._worker = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()
