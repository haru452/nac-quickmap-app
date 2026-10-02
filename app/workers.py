"""UI から切り離したバックグラウンド処理。"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from app import fetcher


class FetchWorker(QThread):
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, url: str, parent=None) -> None:
        super().__init__(parent)
        self._url = url

    def run(self) -> None:
        try:
            data = fetcher.fetch_metadata(self._url)
        except ValueError as exc:
            self.failed.emit(str(exc))
        except fetcher.FetchError as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(data)
