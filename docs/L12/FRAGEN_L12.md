# FRAGEN_L12 — Fragen und Erkenntnisse zu den Seiten G2 (Box, Stand 10.10.2026)

Alles ist Entwurf, bis VSC es im Browser fährt — vor allem die **Kamera** (`BarcodeDetector`), die ich nicht ausprobieren konnte.

| Nr. | Punkt | Entscheidung / Frage | Antwort |
|---|---|---|---|
| 1 | Quelle eines Scans | `scan_ist_hier` bucht mit Quelle `handy`, auch wenn jemand am Rechner die Nummer eintippt. Gewollt? | |
| 2 | Kostenstelle der Hier-Seite | Aus `Sitzung.kostenstellen_fuer("inventar","scannen")` (Verwalter: alle aktiven, höchstens 200); die zuletzt gewählte merkt das Cookie `inventar_ks` (90 Tage). Bei einer einzigen Kostenstelle gibt es keine Wahl | |
| 3 | Teil-Eingang | Das Mengenfeld erscheint nur bei Art `menge`; bei Einzelstücken kommt der Eingang immer ganz | |
| 4 | Verbindungs-Taste „auch Schadensanzeige anlegen“ | **Nicht gebaut**: `Verbindung(braucht="baustelle", menuepunkte=())` bleibt leer, weil APP den Weg nicht genannt hat. „Schaden melden“ legt nur eine `meldung` mit Status `offen` an | |
| 5 | Zurückziehen | Nur mit `buchen` auf der **Herkunft** (wie im Anwendungsfall). Der Polier am Ziel sieht die Taste nicht und bekommt bei einem Aufruf „kein Recht“ | |
| 6 | Dienste | `Dienst` ist eine lokale Klasse mit den Feldern `name, version, fn, recht, beschreibung`; `DIENSTE` bleibt Modulkonstante (Kommentar `AP-K2`). Der Kern hat das Feld noch nicht | |
| 7 | QR-Ziel | `/inventar/s/{nr}` findet auch die Seriennummer, `/inventar/s?nummer=` ist der Rückfall der Scan-Seite ohne Skript. Unbekanntes gibt „kein Recht“ (N7). Mit `?ks=<id>` zeigt die Stück-Seite die großen Tasten „Ist hier“ / „Abgang nach …“ / „Schaden melden“, wenn `scannen` auf dieser Kostenstelle erlaubt ist | |
| 8 | Erinnerungen | Unverändert seit L10 (`erinnern.py`, Kachel „Transfers überfällig“). Die Hier-Seite zeigt sie nicht eigens | |
| 9 | Foto | Zählt die ersten Bytes der Datei, nicht nur die Angabe des Browsers (JPEG `FF D8 FF`, PNG-Kopf) | |
| 10 | Kamera auf dem Handy | `BarcodeDetector` gibt es nur in Chromium/Android und braucht https. Safari/Firefox fallen auf das Eingabefeld zurück. Ob das für die Poliere reicht oder eine Bibliothek nötig ist (G6), entscheidet der Probelauf | |
