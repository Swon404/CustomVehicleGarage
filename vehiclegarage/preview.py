"""Decode downloaded preview images using Windows' built-in GDI+."""

import ctypes
import os
import tempfile
from ctypes import wintypes


class _StartupInput(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_uint32),
        ("callback", ctypes.c_void_p),
        ("suppress_thread", ctypes.c_int),
        ("suppress_codecs", ctypes.c_int),
    ]


class _Rect(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int), ("width", ctypes.c_int), ("height", ctypes.c_int)]


class _BitmapData(ctypes.Structure):
    _fields_ = [
        ("width", ctypes.c_uint32), ("height", ctypes.c_uint32), ("stride", ctypes.c_int),
        ("format", ctypes.c_int), ("scan", ctypes.c_void_p), ("reserved", ctypes.c_size_t),
    ]


def decode(data: bytes) -> bytes:
    """Return PPM data suitable for Tk; PNG/GIF also work without this decoder."""
    if os.name != "nt":
        raise ValueError("JPEG preview decoding is available on Windows only")
    gdip = ctypes.WinDLL("gdiplus")
    gdip.GdiplusStartup.argtypes = [ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(_StartupInput), ctypes.c_void_p]
    gdip.GdiplusShutdown.argtypes = [ctypes.c_size_t]
    gdip.GdipLoadImageFromFile.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
    gdip.GdipDisposeImage.argtypes = [ctypes.c_void_p]
    gdip.GdipGetImageWidth.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    gdip.GdipGetImageHeight.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    gdip.GdipBitmapLockBits.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(_Rect), ctypes.c_uint, ctypes.c_int, ctypes.POINTER(_BitmapData)
    ]
    gdip.GdipBitmapUnlockBits.argtypes = [ctypes.c_void_p, ctypes.POINTER(_BitmapData)]
    token = ctypes.c_size_t()
    startup = _StartupInput(1, None, 0, 0)
    if gdip.GdiplusStartup(ctypes.byref(token), ctypes.byref(startup), None):
        raise ValueError("Windows image decoder could not start")
    try:
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as file:
            file.write(data)
            path = file.name
        image = ctypes.c_void_p()
        try:
            if gdip.GdipLoadImageFromFile(path, ctypes.byref(image)):
                raise ValueError("Preview image format is not supported")
            try:
                width, height = ctypes.c_uint32(), ctypes.c_uint32()
                if gdip.GdipGetImageWidth(image, ctypes.byref(width)) or gdip.GdipGetImageHeight(image, ctypes.byref(height)):
                    raise ValueError("Could not read preview dimensions")
                if not width.value or not height.value or width.value * height.value > 2_000_000:
                    raise ValueError("Preview image dimensions are too large")
                rect = _Rect(0, 0, width.value, height.value)
                bitmap = _BitmapData()
                if gdip.GdipBitmapLockBits(image, ctypes.byref(rect), 1, 0x26200A, ctypes.byref(bitmap)):
                    raise ValueError("Could not decode preview image")
                try:
                    pixels = bytearray()
                    for y in range(height.value):
                        row = ctypes.string_at(bitmap.scan + y * bitmap.stride, width.value * 4)
                        for x in range(0, len(row), 4):
                            pixels.extend((row[x + 2], row[x + 1], row[x]))
                    return f"P6\n{width.value} {height.value}\n255\n".encode("ascii") + pixels
                finally:
                    gdip.GdipBitmapUnlockBits(image, ctypes.byref(bitmap))
            finally:
                gdip.GdipDisposeImage(image)
        finally:
            os.unlink(path)
    finally:
        gdip.GdiplusShutdown(token)
