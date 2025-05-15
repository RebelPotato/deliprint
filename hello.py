import usb
import contextlib
import trio
from typing import Tuple, List
from PIL import Image
from collections.abc import Iterable
from constants import *
import dither

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
    assert width * height == len(image), "Image size mismatch"
    assert width * height <= 64 * 64, "Image too large"
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



def image_to_rows(image: Image.Image) -> Iterable[bytes]:
    """Convert a grayscale image to rows of bytes."""
    width, height = image.size
    for j in range(height):
        yield bytes([image.getpixel((i, j)) for i in range(width)])


def encode(rows: Iterable[bytes]) -> Iterable[bytes]:
    """encode <= 0x3f into 0b1, other into 0b0"""
    for row in rows:
        encoded = []
        count = 0
        for (i, byte) in enumerate(row):
            count *= 2
            if byte <= 0x3f:
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


async def print_rows(rows: Iterable[bytes], endpoint, batch_height: int):
    for batch in batched(encode(rows), batch_height):
        image = b"".join(batch)
        command = prepare_image(image, BYTE_WIDTH, len(batch))
        endpoint.write(command)

def to_image(rows: Iterable[bytes]) -> Image.Image:
    """Convert rows of bytes back to an image."""
    data = []
    height = 0
    for row in rows:
        assert len(row) == WIDTH, "Row length mismatch"
        data.extend(row)
        height += 1
    im = Image.new("L", (WIDTH, height))
    im.putdata(data)
    return im


async def main():
    # with open_deli(idVendor=0x09C5, idProduct=0x0668) as endpoint:
    #     endpoint.write(b"\x1b\x40") # Initialize printer
    #     endpoint.write(black(BYTE_WIDTH, 64))
    #     endpoint.write(white(BYTE_WIDTH, 64))
    #     await trio.sleep(0.5)

    im = Image.open(".scrap/常陸茉子.JPG")
    im = im.resize((WIDTH, im.height * WIDTH // im.width))
    rows = dither.blue_noise(image_to_rows(im.convert("L")))
    to_image(rows).show()
        # await print_rows(rows, endpoint, 32)

        # await trio.sleep(0.5)
        # endpoint.write(white(BYTE_WIDTH, 64))
        # endpoint.write(black(BYTE_WIDTH, 64))
        # endpoint.write(white(BYTE_WIDTH, 64))
        # endpoint.write(white(BYTE_WIDTH, 64))


if __name__ == "__main__":
    trio.run(main)
