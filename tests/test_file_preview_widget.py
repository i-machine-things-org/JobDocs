"""Tests for FilePreviewWidget's bounded image decode (issue #288).
Requires a real (offscreen) QApplication since it exercises real Qt image I/O.
"""

import os

import pytest

pytest.importorskip("PyQt6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QImage  # noqa: E402
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
