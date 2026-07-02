from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget


class LatencyGraph(QWidget):
    def __init__(self, max_points: int = 50):
        super().__init__()
        self._max_points = max_points
        self._values = []
        self.setMinimumHeight(90)

    def add_value(self, value: float):
        self._values.append(value)
        if len(self._values) > self._max_points:
            self._values.pop(0)
        self.update()

    def clear(self):
        self._values = []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window())

        if len(self._values) < 2:
            painter.end()
            return

        width = self.width()
        height = self.height()
        margin = 6
        max_val = max(self._values)
        min_val = min(self._values)
        span = max(max_val - min_val, 1)
        step_x = width / (self._max_points - 1)
        offset = self._max_points - len(self._values)

        pen = QPen(self.palette().highlight().color())
        pen.setWidth(2)
        painter.setPen(pen)

        points = []
        for i, value in enumerate(self._values):
            x = (offset + i) * step_x
            y = height - margin - ((value - min_val) / span) * (height - 2 * margin)
            points.append((x, y))

        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])

        painter.end()
