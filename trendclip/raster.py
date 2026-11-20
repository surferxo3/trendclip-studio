"""Tiny dependency-free scene rasterizer with an original 5x7 block typeface."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple


Glyph = Tuple[str, ...]
RGB = Tuple[int, int, int]


FONT: Dict[str, Glyph] = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "|": ("00100", "00100", "00100", "00100", "00100", "00100", "00100"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ":": ("00000", "00100", "00100", "00000", "00100", "00100", "00000"),
    ",": ("00000", "00000", "00000", "00000", "00100", "00100", "01000"),
    "•": ("00000", "00000", "01110", "01110", "01110", "00000", "00000"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    " ": ("00000",) * 7,
}


def color(value: str) -> RGB:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


class Canvas:
    def __init__(self, width: int, height: int, top: RGB, bottom: RGB = (3, 5, 10)) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(width * height * 3)
        for y in range(height):
            ratio = y / max(1, height - 1)
            pixel = bytes(round(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
            start = y * width * 3
            self.pixels[start : start + width * 3] = pixel * width

    def rectangle(self, x: int, y: int, width: int, height: int, fill: RGB, opacity: float = 1.0) -> None:
        left, top = max(0, x), max(0, y)
        right, bottom = min(self.width, x + width), min(self.height, y + height)
        for py in range(top, bottom):
            for px in range(left, right):
                offset = (py * self.width + px) * 3
                for channel in range(3):
                    old = self.pixels[offset + channel]
                    self.pixels[offset + channel] = round(old * (1 - opacity) + fill[channel] * opacity)

    def text(self, value: str, x: int, y: int, scale: int, fill: RGB, max_width: int) -> int:
        value = value.upper()
        if value:
            scale = max(2, min(scale, max_width // max(1, len(value) * 6 - 1)))
        cursor = x
        for character in value:
            glyph = FONT.get(character, FONT["?"])
            for row, bits in enumerate(glyph):
                for column, bit in enumerate(bits):
                    if bit == "1":
                        self.rectangle(cursor + column * scale, y + row * scale, scale, scale, fill)
            cursor += 6 * scale
        return scale

    def write_ppm(self, destination: Path) -> None:
        header = f"P6\n{self.width} {self.height}\n255\n".encode("ascii")
        with destination.open("wb") as stream:
            stream.write(header)
            stream.write(self.pixels)


def render_scene(
    destination: Path,
    *,
    width: int,
    height: int,
    background: str,
    accent: str,
    eyebrow: str,
    headline: str,
    body: str,
    index: int,
    count: int,
) -> None:
    accent_rgb = color(accent)
    canvas = Canvas(width, height, color(background))
    for x in range(0, width, 180):
        canvas.rectangle(x, 0, 2, height, (255, 255, 255), 0.045)
    for y in range(0, height, 180):
        canvas.rectangle(0, y, width, 2, (255, 255, 255), 0.045)
    canvas.rectangle(0, 0, 38, height, accent_rgb)
    canvas.rectangle(90, 180, 180, 12, accent_rgb)
    canvas.text(eyebrow, 90, 235, 6, accent_rgb, 900)
    lines = headline.splitlines()
    start_y = 800 - (len(lines) - 1) * 80
    for line_index, line in enumerate(lines):
        canvas.text(line, 90, start_y + line_index * 150, 16, (255, 255, 255), 900)
    canvas.rectangle(90, 1530, 900, 2, (255, 255, 255), 0.28)
    canvas.text(body, 90, 1585, 6, (215, 220, 230), 900)
    canvas.text("TRENDCLIP STUDIO", 90, 1760, 4, (130, 138, 150), 600)
    counter = f"{index + 1:02d} / {count:02d}"
    counter_scale = 4
    counter_width = (len(counter) * 6 - 1) * counter_scale
    canvas.text(counter, 990 - counter_width, 1760, counter_scale, (130, 138, 150), 300)
    canvas.write_ppm(destination)

