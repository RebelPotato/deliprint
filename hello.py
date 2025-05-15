import usb
import contextlib
import trio
from typing import Tuple

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
    return prepare_image(b"\xFF" * (width * height), width, height)

def checkerboard(size: int, i: int, j: int) -> int:
    x = i // size
    y = j // (8 * size)
    return 0xFF if x % 2 == y % 2 else 0x00


async def main():
    with open_deli(idVendor=0x09C5, idProduct=0x0668) as endpoint:
        width = 48
        height = 8
        endpoint.write(b"\x1b\x40")  # Initialize printer
        endpoint.write(black(width, 64))
        endpoint.write(white(width, 64))
        
        for w in range(1, width * 3 // 2):
            image = []
            for j in range(height):
                for i in range(w):
                    image.append(checkerboard(1, i, j))
            endpoint.write(prepare_image(bytes(image), w, height))
        
        endpoint.write(white(width, 64))
        endpoint.write(black(width, 64))
        endpoint.write(white(width, 128))


if __name__ == "__main__":
    trio.run(main)
