from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


class JsonSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document) -> None:
        super().__init__(document)
        self._enabled = False

        self._key_format = QTextCharFormat()
        self._key_format.setForeground(QColor("#0550ae"))

        self._string_format = QTextCharFormat()
        self._string_format.setForeground(QColor("#0a7c42"))

        self._number_format = QTextCharFormat()
        self._number_format.setForeground(QColor("#0550ae"))

        self._literal_format = QTextCharFormat()
        self._literal_format.setForeground(QColor("#953800"))
        self._literal_format.setFontWeight(QFont.Weight.Bold)

        self._punctuation_format = QTextCharFormat()
        self._punctuation_format.setForeground(QColor("#57606a"))

        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = [
            (QRegularExpression(r'"([^"\\]|\\.)*"(?=\s*:)'), self._key_format),
            (QRegularExpression(r'"([^"\\]|\\.)*"'), self._string_format),
            (QRegularExpression(r"\b-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?\b"), self._number_format),
            (QRegularExpression(r"\b(true|false|null)\b"), self._literal_format),
            (QRegularExpression(r"[{}\[\]:,]"), self._punctuation_format),
        ]

    def set_enabled(self, enabled: bool) -> None:
        if self._enabled == enabled:
            return
        self._enabled = enabled
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        if not self._enabled:
            return

        for pattern, fmt in self._rules:
            match = pattern.match(text)
            index = match.capturedStart()
            while index >= 0:
                length = match.capturedLength()
                self.setFormat(index, length, fmt)
                match = pattern.match(text, index + length)
                index = match.capturedStart()
