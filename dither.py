from PIL import Image
from collections.abc import Iterable
from typing import List, Tuple
from constants import *
import functools

def bayer8_at(i: int, j: int) -> int:
    mat = [
        [0, 32, 8, 40, 2, 34, 10, 42],
        [48, 16, 56, 24, 50, 18, 58, 26],
        [12, 44, 4, 36, 14, 46, 6, 38],
        [60, 28, 52, 20, 62, 30, 54, 22],
        [3, 35, 11, 43, 1, 33, 9, 41],
        [51, 19, 59, 27, 49, 17, 57, 25],
        [15, 47, 7, 39, 13, 45, 5, 37],
        [63, 31, 55, 23, 62, 30, 54, 22]
    ]
    x = i % 8
    y = j % 8
    return mat[y][x] * 4
    
def bayer8(rows: Iterable[bytes]) -> Iterable[bytes]:
    """
    Apply Bayer dithering to the image rows.
    """
    for j, row in enumerate(rows):
        dithered = bytearray()
        for i, byte in enumerate(row):
            dithered.append(0xFF if byte >= bayer8_at(i, j) else 0x00)
        yield bytes(dithered)

def floyd_steinberg(rows: Iterable[bytes]) -> Iterable[bytes]:
    """
    Apply Floyd-Steinberg dithering to the image rows.
    """
    errors0 = [0] * WIDTH
    errors1 = [0] * WIDTH
    for row in rows:
        for i in range(WIDTH):
            total = row[i] + errors0[i]
            errors0[i] = 0xFF if total > 0x3F else 0x00
            error = (total - errors0[i]) // 16
            if i < WIDTH - 1:
                errors0[i + 1] += error * 7
                errors1[i + 1] += error
            if i > 0:
                errors1[i - 1] += error * 3
            errors1[i] += error * 5
        yield bytes(errors0)
        errors0 = errors1
        errors1 = [0] * WIDTH

def atkinson(rows: Iterable[bytes]) -> Iterable[bytes]:
    """
    Apply Atkinson dithering to the image rows.
    """
    errors0 = [0] * WIDTH
    errors1 = [0] * WIDTH
    errors2 = [0] * WIDTH
    for row in rows:
        for i in range(WIDTH):
            total = row[i] + errors0[i]
            errors0[i] = 0xFF if total > 0x3F else 0x00
            error = (total - errors0[i]) // 8
            if i < WIDTH - 1:
                errors0[i + 1] += error
            if i < WIDTH - 2:
                errors0[i + 2] += error
            if i > 0:
                errors1[i - 1] += error
            errors1[i] += error
            if i < WIDTH - 1:
                errors1[i + 1] += error
            errors2[i] += error
        yield bytes(errors0)
        errors0 = errors1
        errors1 = errors2
        errors2 = [0] * WIDTH

@functools.cache
def blue_noise_mat() -> Tuple[int, List[List[int]]]:
    im = Image.open("assets/blue_LDR_LLL1_0.png")
    assert im.width == im.height
    side = im.width
    mat = []
    for j in range(side):
        row = []
        for i in range(side):
            row.append(im.getpixel((i, j))[0])
        mat.append(row)
    return side, mat

def blue_noise_at(i: int, j: int) -> int:
    side, mat = blue_noise_mat()
    return mat[j%side][i%side]

def blue_noise(rows: Iterable[bytes]) -> Iterable[bytes]:
    """
    Apply blue noise dithering to the image rows.
    """
    for j, row in enumerate(rows):
        dithered = bytearray()
        for i, byte in enumerate(row):
            dithered.append(0xFF if byte > blue_noise_at(i, j) else 0x00)
        yield bytes(dithered)