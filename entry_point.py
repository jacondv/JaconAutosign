"""Entry point rieng cho PyInstaller - autosign/main.py dung relative import
nen khong chay duoc truc tiep nhu 1 script top-level, phai qua wrapper nay."""
import sys

from autosign.main import main

if __name__ == "__main__":
    sys.exit(main())
