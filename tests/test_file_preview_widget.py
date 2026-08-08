"""Tests for FilePreviewWidget's bounded image decode (issue #288).
Requires a real (offscreen) QApplication since it exercises real Qt image I/O.

Note on PNG vs. JPEG coverage: QImageReader.setScaledSize() only bounds the
actual *decode* for formats whose Qt plugin supports native scaled reading
(JPEG). PNG does not support it on this Qt build, so a PNG-only test suite
can't distinguish a genuinely bounded decode from a full-decode-then-scale
fallback — both produce an identically-sized final pixmap. The JPEG tests
below (TestBoundedDecodeIsFormatSpecific) exist specifically to catch a
regression to the full-decode-then-scale path, which the PNG tests cannot.
"""

import os
import subprocess
import sys

import pytest

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QImage, QImageIOHandler, QImageReader  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from shared.widgets import FilePreviewWidget  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_png(path, width, height):
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    assert image.save(str(path), "PNG")


def _make_jpeg(path, width, height):
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    assert image.save(str(path), "JPEG", 90)


class TestLoadBoundedImage:
    def test_large_image_is_downscaled_to_max_dim(self, qapp, tmp_path):
        img_path = tmp_path / 'large.png'
        _make_png(img_path, 4000, 3000)

        widget = FilePreviewWidget()
        pix = widget._load_bounded_image(str(img_path))

        assert pix is not None and not pix.isNull()
        assert pix.width() <= FilePreviewWidget._PREVIEW_MAX_DIM
        assert pix.height() <= FilePreviewWidget._PREVIEW_MAX_DIM
        # Aspect ratio preserved (4000:3000 == 4:3)
        assert abs(pix.width() / pix.height() - 4000 / 3000) < 0.02

    def test_small_image_is_not_upscaled(self, qapp, tmp_path):
        img_path = tmp_path / 'small.png'
        _make_png(img_path, 100, 80)

        widget = FilePreviewWidget()
        pix = widget._load_bounded_image(str(img_path))

        assert pix is not None and not pix.isNull()
        assert pix.width() == 100
        assert pix.height() == 80

    def test_invalid_path_returns_none(self, qapp, tmp_path):
        widget = FilePreviewWidget()
        pix = widget._load_bounded_image(str(tmp_path / 'does_not_exist.png'))
        assert pix is None

    def test_preview_file_uses_bounded_decode_for_images(self, qapp, tmp_path):
        img_path = tmp_path / 'large.jpg'
        _make_png(img_path, 3000, 3000)  # extension drives dispatch, not content

        widget = FilePreviewWidget()
        widget.preview_file(str(img_path))

        assert widget._pixmap is not None
        assert widget._pixmap.width() <= FilePreviewWidget._PREVIEW_MAX_DIM
        assert widget._pixmap.height() <= FilePreviewWidget._PREVIEW_MAX_DIM


class TestBoundedDecodeIsFormatSpecific:
    """PNG-only coverage can't tell a genuinely bounded decode apart from a
    full-decode-then-scale fallback, since both yield an identically-sized
    final pixmap (see module docstring). These tests use JPEG — the one
    format in _IMAGE_EXTS whose Qt plugin actually supports native scaled
    reading — to verify the bounded path is really being taken.
    """

    def test_jpeg_supports_native_scaled_read(self, qapp, tmp_path):
        # This is the mechanism _load_bounded_image() depends on. If it's
        # ever False on a target Qt build, setScaledSize() silently falls
        # back to full-res decode + software scale for JPEG too.
        img_path = tmp_path / 'probe.jpg'
        _make_jpeg(img_path, 64, 64)
        reader = QImageReader(str(img_path))
        assert reader.supportsOption(QImageIOHandler.ImageOption.ScaledSize) is True

    def test_png_does_not_support_native_scaled_read(self, qapp, tmp_path):
        # Documents the negative case the JPEG-only decode-bound claim rests
        # on — if this ever flips True on some Qt build, the docstring/
        # CODING_NOTES caveat about PNG needs revisiting, not just this test.
        img_path = tmp_path / 'probe.png'
        _make_png(img_path, 64, 64)
        reader = QImageReader(str(img_path))
        assert reader.supportsOption(QImageIOHandler.ImageOption.ScaledSize) is False

    def test_large_jpeg_decode_memory_is_bounded(self, qapp, tmp_path):
        """Measures actual peak RSS (VmHWM) around the decode call in a
        subprocess, so an unrelated baseline (QApplication/import overhead)
        can't mask the delta. A large JPEG decoded through the bounded path
        should cost only a few MB; a full-res 4000x3000 decode (the
        pre-fix / fallback behavior) needs ~48 MB just for the raw RGB32
        buffer. If this regresses to a full decode, the delta jumps well
        past the threshold below.
        """
        img_path = tmp_path / 'large.jpg'
        _make_jpeg(img_path, 4000, 3000)

        probe = f'''
import sys
def vmhwm_kb():
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmHWM:"):
                return int(line.split()[1])
    return -1

from PyQt6.QtGui import QImageReader
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)

reader = QImageReader({str(img_path)!r})
reader.setAutoTransform(True)
size = reader.size()
MAX_DIM = {FilePreviewWidget._PREVIEW_MAX_DIM}
scale = min(MAX_DIM / size.width(), MAX_DIM / size.height(), 1.0)
if scale < 1.0:
    reader.setScaledSize(QSize(max(1, round(size.width() * scale)), max(1, round(size.height() * scale))))

before = vmhwm_kb()
image = reader.read()
after = vmhwm_kb()
assert not image.isNull()
print(after - before)
'''
        if not os.environ.get('DISPLAY') and not os.environ.get('QT_QPA_PLATFORM'):
            pytest.skip("no display/offscreen platform configured for subprocess probe")

        result = subprocess.run(
            [sys.executable, '-c', probe],
            capture_output=True, text=True,
            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, f"probe failed: {result.stderr}"
        delta_kb = int(result.stdout.strip().splitlines()[-1])

        # Bounded JPEG decode measured ~2.8 MB in manual testing; a full-res
        # fallback would be ~48+ MB. Use a generous 20 MB cutoff so this
        # isn't flaky across allocators/platforms while still clearly
        # catching a regression to the unbounded path.
        assert delta_kb < 20_000, (
            f"JPEG decode used {delta_kb} KB peak RSS — expected a bounded "
            f"decode (a few MB); this large a jump suggests setScaledSize() "
            f"silently fell back to full-res decode + software scale"
        )
