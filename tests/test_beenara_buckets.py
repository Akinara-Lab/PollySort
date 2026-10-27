"""Risiko-Schwellen je Listengröße: die Laufzeiten nehmen die Buckets aus der Kalibrierdatei.

BeeNara v0.4 fasst große Bäume zu „200+“ zusammen und schreibt seine Buckets in die Kalibrierung;
ältere Kalibrierungen ohne ``buckets`` behalten die festen Buckets bis „300+“.
"""

from __future__ import annotations

import pytest

from pollysort import beenara_big_laufzeit, beenara_laufzeit

V04 = [[3, 9], [10, 24], [25, 49], [50, 99], [100, 199], [200, None]]


@pytest.mark.parametrize("modul", [beenara_laufzeit, beenara_big_laufzeit])
@pytest.mark.parametrize(("n", "erwartet"), [(2, "3-9"), (9, "3-9"), (10, "10-24"), (199, "100-199"),
                                              (250, "200-299"), (300, "300+"), (900, "300+")])
def test_ohne_buckets_in_der_kalibrierung_wie_bisher(modul, n, erwartet):
    assert modul.bucket(n) == erwartet
    assert modul.bucket(n, None) == erwartet


@pytest.mark.parametrize("modul", [beenara_laufzeit, beenara_big_laufzeit])
@pytest.mark.parametrize(("n", "erwartet"), [(2, "3-9"), (9, "3-9"), (24, "10-24"), (200, "200+"),
                                              (250, "200+"), (900, "200+")])
def test_buckets_aus_der_kalibrierung(modul, n, erwartet):
    assert modul.bucket(n, V04) == erwartet


def test_ohne_offenes_ende_zaehlt_der_letzte_bucket():
    assert beenara_laufzeit.bucket(40, [[3, 9], [10, 24]]) == "10-24"
