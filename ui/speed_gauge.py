from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class SpeedGauge(QWidget):
    def __init__(self, label: str, max_value: float = 200):
        super().__init__()
        self._label = label
        self._max_value = max_value
        self._value = 0.0
        self.setMinimumSize(160, 130)

    def set_value(self, value: float):
        self._value = value
        if value > self._max_value:
            self._max_value = value * 1.2
        self.update()

    def reset(self):
        self._value = 0.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        side = min(self.width() - 20, (self.height() - 20) * 2)
        rect = QRectF((self.width() - side) / 2, 10, side, side)

        pen_bg = QPen(self.palette().mid().color(), 12, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen_bg)
        painter.drawArc(rect, 180 * 16, -180 * 16)

        ratio = max(0.0, min(self._value / self._max_value, 1.0)) if self._max_value else 0.0
        pen_value = QPen(self.palette().highlight().color(), 12, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen_value)
        painter.drawArc(rect, 180 * 16, int(-180 * 16 * ratio))

        painter.setPen(self.palette().text().color())
        value_font = QFont()
        value_font.setPointSize(13)
        value_font.setBold(True)
        painter.setFont(value_font)
        painter.drawText(self.rect().adjusted(0, 0, 0, -18), Qt.AlignCenter, f"{self._value:.1f}")

        label_font = QFont()
        label_font.setPointSize(9)
        painter.setFont(label_font)
        painter.drawText(
            self.rect().adjusted(0, self.height() - 22, 0, 0),
            Qt.AlignHCenter | Qt.AlignTop,
            f"{self._label} (Mbps)",
        )

        painter.end()
