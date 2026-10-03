"""Das Flugbrett — die Browser-Oberfläche von PollySort.

Das Flugbrett ist das Brett vor dem Flugloch, auf dem die Bienen landen und starten. Hier
ist es eine lokale Web-Oberfläche auf demselben Kern wie die Konsole: ``pollysort-web``
(oder ``oberflaeche`` in der Konsole) startet einen kleinen Server auf ``127.0.0.1`` und
öffnet den Browser.

- ``konsole``  — ``WebKonsole``: der Ausgabe-Layer des Kerns als Ereignisstrom.
- ``dienst``   — ``Dienst``: alle Aktionen als Funktionen mit JSON-Ergebnis.
- ``server``   — HTTP-Server (nur Standardbibliothek), Token-Schutz, Ereignis-Stream.
- ``static/``  — die Seite selbst: HTML, CSS, Pixel-Schrift & Sprites, ohne Fremd-Code.
"""
