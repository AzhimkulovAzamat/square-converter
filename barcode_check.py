"""Barcode integrity checker."""

from PIL import Image

try:
    from pyzbar import pyzbar as _pyzbar
    _pyzbar.decode(Image.new("RGB", (1, 1)))
    PYZBAR_AVAILABLE = True
except Exception:
    PYZBAR_AVAILABLE = False

STATUS_OK        = "ok"
STATUS_NOT_FOUND = "not_found"
STATUS_DAMAGED   = "damaged"
STATUS_SKIPPED   = "skipped"


class BarcodeIntegrityError(Exception):
    pass


def read_barcodes(img: Image.Image) -> list:
    if not PYZBAR_AVAILABLE:
        return []
    try:
        return [{"type": c.type, "data": c.data} for c in _pyzbar.decode(img)]
    except Exception:
        return []


def verify(original: Image.Image, converted: Image.Image, filename: str = "") -> dict:
    label = f"[{filename}] " if filename else ""

    # pyzbar недоступен — пропускаем проверку, файл считается успешным
    if not PYZBAR_AVAILABLE:
        return {
            "status":          STATUS_SKIPPED,
            "ok":              True,
            "original_codes":  [],
            "converted_codes": [],
            "missing":         [],
            "message":         f"{label}Проверка пропущена (zbar недоступен)",
        }

    orig_codes = read_barcodes(original)
    conv_codes = read_barcodes(converted)

    # Баркод не найден в оригинале
    if not orig_codes:
        return {
            "status":          STATUS_NOT_FOUND,
            "ok":              False,
            "original_codes":  [],
            "converted_codes": conv_codes,
            "missing":         [],
            "message":         f"{label}Штрих-код не найден в файле",
        }

    orig_set = {(c["type"], c["data"]) for c in orig_codes}
    conv_set  = {(c["type"], c["data"]) for c in conv_codes}
    missing   = orig_set - conv_set

    # Баркод был, но после конвертации не читается
    if missing:
        lost = [d.decode(errors="replace") for _, d in missing]
        return {
            "status":          STATUS_DAMAGED,
            "ok":              False,
            "original_codes":  orig_codes,
            "converted_codes": conv_codes,
            "missing":         list(missing),
            "message":         f"{label}Не удалось прочитать штрих-код после конвертации: {', '.join(lost)}",
        }

    # Всё ок
    codes_str = ", ".join(c["data"].decode(errors="replace") for c in orig_codes)
    return {
        "status":          STATUS_OK,
        "ok":              True,
        "original_codes":  orig_codes,
        "converted_codes": conv_codes,
        "missing":         [],
        "message":         f"{label}✓ Штрих-код проверен: {codes_str}",
    }
