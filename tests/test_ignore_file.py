from winsync import sync
from winsync.filters import IGNORE_FILE


def test_winsyncignore_in_source(tmp_path):
    src = tmp_path / "src"
    (src / "Ban nhap").mkdir(parents=True)
    (src / "Ban nhap" / "y-tuong.docx").write_text("nháp", encoding="utf-8")
    (src / "bao-gia.xlsx").write_text("báo giá", encoding="utf-8")
    (src / "anh.psd").write_text("ảnh", encoding="utf-8")
    (src / IGNORE_FILE).write_text("# thư mục nháp của tôi\nBan nhap\n*.psd\n\n", encoding="utf-8")
    res = sync(src, tmp_path / "dst")
    assert [c.rel_path for c in res.changes] == ["bao-gia.xlsx"]
    assert not (tmp_path / "dst" / IGNORE_FILE).exists()  # file cấu hình không bị chép lên máy chủ


def test_no_ignore_file_is_fine(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("a", encoding="utf-8")
    assert sync(src, tmp_path / "dst").copied == 1
