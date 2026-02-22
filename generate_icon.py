#!/usr/bin/env python3
"""
Generates flx4control.ico and flx4control.png in a target directory.
Run after installing dependencies:  python generate_icon.py <target_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    target.mkdir(parents=True, exist_ok=True)

    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QPolygon
        from PySide6.QtCore import Qt, QPoint

        app = QApplication.instance() or QApplication(sys.argv[:1])

        size = 256
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dark navy background circle
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1a1a2e"))
        p.drawEllipse(1, 1, size - 2, size - 2)

        # Green ring
        rw = max(2, size // 18)
        p.setPen(QPen(QColor("#4dffaa"), rw))
        p.setBrush(Qt.BrushStyle.NoBrush)
        m = size // 8
        p.drawEllipse(m, m, size - 2 * m, size - 2 * m)

        # Play triangle (slightly right of center)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#4dffaa"))
        cx = size // 2 + size // 20
        cy = size // 2
        s = size // 5
        poly = QPolygon([
            QPoint(cx - s, cy - s),
            QPoint(cx - s, cy + s),
            QPoint(cx + s, cy),
        ])
        p.drawPolygon(poly)
        p.end()

        png_ok = pix.save(str(target / "flx4control.png"))
        ico_ok = pix.save(str(target / "flx4control.ico"), "ICO")
        print(f"  Icon saved: png={png_ok} ico={ico_ok}  →  {target}")

    except Exception as exc:
        print(f"  Icon generation skipped: {exc}")


if __name__ == "__main__":
    main()
