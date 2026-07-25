"""Tao chung thu so TU KY (self-signed) + anh chu ky tay mau, chi de TEST app.

Day KHONG PHAI chu ky so hop le ve mat phap ly (khong co CA nao xac thuc),
Acrobat/trinh doc PDF se bao "chua duoc tin cay" - dung de kiem tra luong
hoat dong cua phan mem (doc .pfx, ve khung, ky, xuat file) truoc khi co
chung thu so that.

Chay:
    .venv\\Scripts\\python.exe scripts\\generate_test_certificate.py
    .venv\\Scripts\\python.exe scripts\\generate_test_certificate.py --name "Nguyen Van A" --password 123456
"""
from __future__ import annotations

import argparse
import datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from PIL import Image, ImageDraw, ImageFont


def generate_pfx(name: str, password: str, out_path: Path, valid_days: int) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=valid_days))
        .sign(key, hashes.SHA256())
    )
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=name.encode("utf-8"),
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode("utf-8")),
    )
    out_path.write_bytes(pfx_bytes)


def generate_signature_image(name: str, out_path: Path) -> None:
    img = Image.new("RGBA", (400, 150), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except OSError:
        font = ImageFont.load_default()
    draw.text((10, 50), name, fill=(20, 40, 160, 255), font=font)
    draw.line((10, 100, 390, 100), fill=(20, 40, 160, 180), width=2)
    img.save(out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="Nguyen Van A (TEST)", help="Ten hien thi tren chung thu")
    parser.add_argument("--password", default="123456", help="Mat khau bao ve file .pfx")
    parser.add_argument("--out-dir", default="test_assets", help="Thu muc luu ket qua")
    parser.add_argument("--valid-days", type=int, default=365, help="So ngay hieu luc chung thu")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pfx_path = out_dir / "test_cert.pfx"
    sig_path = out_dir / "test_signature.png"

    generate_pfx(args.name, args.password, pfx_path, args.valid_days)
    generate_signature_image(args.name, sig_path)

    print("Da tao xong file test:")
    print(f"  Chung thu so : {pfx_path.resolve()}")
    print(f"  Mat khau     : {args.password}")
    print(f"  Anh chu ky   : {sig_path.resolve()}")
    print("\nCANH BAO: day la chung thu TU KY, chi dung de test, khong co gia tri phap ly.")


if __name__ == "__main__":
    main()
