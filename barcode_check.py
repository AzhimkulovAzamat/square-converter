"""Barcode integrity checker."""

from PIL import Image

try:
    from pyzbar import pyzbar as _pyzbar
    _pyzbar.decode(Image.new("RGB", (1, 1)))
    PYZBAR_AVAILABLE = True
except Exception:
    PYZBAR_AVAILABLE = False


class BarcodeIntegrityError(Exception):
    pass


# Status constants
STATUS_OK        = "ok"          # barcode found and intact after conversion
STATUS_NOT_FOUND = "not_found"   # no barcode detected in original at all
STATUS_DAMAGED   = "damaged"     # barcode was in original but lost/unreadable after conversion
STATUS_SKIPPED   = "skipped"     # pyzbar unavailable, check skipped


def read_barcodes(img: Image.Image) -> list:
    if not PYZBAR_AVAILABLE:
        return []
    try:
        return [{"type": c.type, "data": c.data} for c in _pyzbar.decode(img)]
    except Exception:
        return []


def verify(original: Image.Image, converted: Image.Image, filename: str = "") -> dict:
    """
    Returns dict:
      status:          ok | not_found | damaged | skipped
      ok:              True only when status == ok or status == skipped
      original_codes:  list of {type, data}
      converted_codes: list of {type, data}
      missing:         codes present in original but gone after conversion
      message:         human-readable Russian message for the UI
    """
    label = f"[{filename}] " if filename else ""

    if not PYZBAR_AVAILABLE:
        return {
            "status": STATUS_SKIPPED,
            "ok": True,
            "original_codes": [],
            "converted_codes": [],
            "missing": [],
            "message": "Проверка штрих-кода пропущена (pyzbar недоступен)",
        }

    orig_codes = read_barcodes(original)
    conv_codes = read_barcodes(converted)

    # Case 1: no barcode in original at all
    if not orig_codes:
        return {
            "status": STATUS_NOT_FOUND,
            "ok": False,
            "original_codes": [],
            "converted_codes": conv_codes,
            "missing": [],
            "message": f"{label}Штрих-код не найден в файле",
        }

    orig_set = {(c["type"], c["data"]) for c in orig_codes}
    conv_set = {(c["type"], c["data"]) for c in conv_codes}
    missing  = orig_set - conv_set

    # Case 2: barcode existed but damaged/lost after conversion
    if missing:
        lost = [d.decode(errors="replace") for _, d in missing]
        return {
            "status": STATUS_DAMAGED,
            "ok": False,
            "original_codes": orig_codes,
            "converted_codes": conv_codes,
            "missing": list(missing),
            "message": f"{label}Не удалось прочитать штрих-код после конвертации: {', '.join(lost)}",
        }

    # Case 3: all good
    codes_str = ", ".join(c["data"].decode(errors="replace") for c in orig_codes)
    return {
        "status": STATUS_OK,
        "ok": True,
        "original_codes": orig_codes,
        "converted_codes": conv_codes,
        "missing": [],
        "message": f"{label}✓ Штрих-код проверен: {codes_str}",
    }
