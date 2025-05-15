import usb
import contextlib
import trio
from typing import Tuple, List
from PIL import Image
from collections.abc import Iterable

import snoop


@contextlib.contextmanager
def open_deli(idVendor: int, idProduct: int):
    """Open the Deli USB printer and yield the endpoint object."""
    printer = usb.core.find(idVendor=idVendor, idProduct=idProduct)
    assert printer is not None, "Printer not found"
    try:
        printer.set_configuration()
        cfg = printer.get_active_configuration()
        interface = cfg[(0, 0)]  # First interface
        endpoint = usb.util.find_descriptor(
            interface,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_OUT,
        )
        yield endpoint
    finally:
        usb.util.release_interface(printer, interface)
        usb.util.dispose_resources(printer)


def low_high(value: int) -> Tuple[int, int]:
    """Return the low and high byte of a value."""
    assert 0 <= value < 65536, "Value out of 2 byte range"
    return value & 0xFF, (value >> 8) & 0xFF


def prepare_image(image: bytes, width: int, height: int) -> bytes:
    x_low, x_high = low_high(width)
    y_low, y_high = low_high(height)
    command = b"\x1d\x76\x30\x00"  # GS v 0, normal mode
    command += bytes([x_low, x_high, y_low, y_high])
    command += image
    return command


def white(width: int, height: int) -> bytes:
    return prepare_image(b"\x00" * (width * height), width, height)


def black(width: int, height: int) -> bytes:
    return prepare_image(b"\xDD" * (width * height), width, height)


def checkerboard(size: int, i: int, j: int) -> int:
    x = i // size
    y = j // (8 * size)
    return 0xFF if x % 2 == y % 2 else 0x00


BYTE_WIDTH = 48
WIDTH = BYTE_WIDTH * 8

def image_to_rows(image: Image.Image) -> Iterable[bytes]:
    """Convert a grayscale image to rows of bytes."""
    width, height = image.size
    for j in range(height):
        yield bytes([image.getpixel((i, j)) for i in range(width)])

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
            errors0[i] = 0xFF if total >= 0x3F else 0x00
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

def encode(rows: Iterable[bytes]) -> Iterable[bytes]:
    """encode 0x00 into 0b1, other into 0b0"""
    for row in rows:
        encoded = []
        count = 0
        for (i, byte) in enumerate(row):
            count *= 2
            if byte == 0x00:
                count += 1
            if i % 8 == 7:
                encoded.append(count)
                count = 0
        if len(row) % 8 != 0:
            encoded.append(count)
        yield bytes(encoded)
            

def batched(rows: Iterable[bytes], batch_size: int) -> Iterable[List[bytes]]:
    batch = []
    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if len(batch) > 0:
        yield batch


async def write_image(rows: Iterable[bytes], endpoint, batch_height: int):
    for batch in batched(encode(rows), batch_height):
        image = b"".join(batch)
        command = prepare_image(image, BYTE_WIDTH, batch_height)
        endpoint.write(command)


async def main():
    with open_deli(idVendor=0x09C5, idProduct=0x0668) as endpoint:
        endpoint.write(b"\x1b\x40") # Initialize printer
        endpoint.write(black(BYTE_WIDTH, 64))
        endpoint.write(white(BYTE_WIDTH, 64))
        await trio.sleep(0.5)

        im = Image.open(".scrap/常陸茉子.JPG")
        im = im.resize((WIDTH, im.height * WIDTH // im.width))
        await write_image(bayer8(image_to_rows(im.convert("L"))), endpoint, 32)
        # await write_image(atkinson(image_to_rows(im.convert("L"))), endpoint, 32)
        # await write_image(image_to_rows(im.convert("1")), endpoint, 32)

        await trio.sleep(0.5)
        endpoint.write(white(BYTE_WIDTH, 64))
        endpoint.write(black(BYTE_WIDTH, 64))
        endpoint.write(white(BYTE_WIDTH, 64))
        endpoint.write(white(BYTE_WIDTH, 64))


if __name__ == "__main__":
    trio.run(main)
