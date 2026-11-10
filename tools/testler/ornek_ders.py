"""Testler için örnek dersi geçici olarak kurar.

Program derssiz gelir; testlerin kullandığı peri-implantitis dersi ornek-dersler/ klasöründedir.
kur() onu lessons/ altına kopyalar (zaten kuruluysa dokunmaz), kaldir() yalnız kendi kopyaladığını siler.
Ders listesine (katalog) eklenmez.
"""
import os
import shutil

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DERS = "peri-implantitis-cerrahi"
KAYNAK = os.path.join(KOK, "ornek-dersler", DERS)
HEDEF = os.path.join(KOK, "lessons", DERS)
_kopyaladim = []


def kur():
    if not os.path.isdir(HEDEF):
        shutil.copytree(KAYNAK, HEDEF)
        _kopyaladim.append(HEDEF)
    return HEDEF


def kaldir():
    while _kopyaladim:
        shutil.rmtree(_kopyaladim.pop(), ignore_errors=True)
