# FRAGEN_L5 — Box an GER/Thomas

Stand 08.10.2026.

| Nr. | Frage | Vorschlag / vorläufig angenommen |
|---|---|---|
| 1 | Seite `bauteile`: Der Auftrag erklärt sie nicht. | **Vorläufig: Zubehör und Bauteile eines Hauptstücks** (Löffel zum Bagger, vgl. B12). Bitte bestätigen oder korrigieren; die drei Hilfetexte sind sonst anzupassen. |
| 2 | Ist der Bogen „70 × 36 mm, 24 je A4" (Rand oben 4,5 mm, links 0) der tatsächlich bestellte Etikettenbogen? | **Vorläufig: ja** (Standard laut Auftrag). Bitte Datenblatt des Bogens prüfen und einen Probedruck mit WeasyPrint machen. |
| 3 | Maximale Länge der Bezeichnung auf dem Etikett. | **Vorläufig 48 Zeichen** (2 Zeilen × etwa 24 bei 8 pt, neben dem QR). Nach Probedruck feinjustieren (`MAX_BEZEICHNUNG`). |
| 4 | Meldungsschlüssel der Module haben den Text `inventar.code.<schlüssel>`. Einzelheiten kommen als `{detail}`. Texte wie „{nr} braucht eine Stellenzahl" enthalten wörtliche geschweifte Klammern. | **Vorläufig: so.** Wenn VSC die Texte mit `str.format` ausfüllt, müssen diese Klammern maskiert oder die Texte ohne Klammern geschrieben werden — bitte VSC sagen, welche Technik er einsetzt. |
| 5 | Wortlaut der Hilfetexte und Tasten: Entwurf von Box im Stil „kurz, neutral, ohne Anrede". | Thomas/GER ändern frei; die Prüffälle X1–X7 sichern nur Form, Vollständigkeit und Stil. |
| 6 | Quelle `import` heißt in den Texten `inventar.quelle.importiert` (weil `import` ein Python-Schlüsselwort ist und für Schlüssel in Vorlagen unpraktisch). | **Vorläufig: so.** |
