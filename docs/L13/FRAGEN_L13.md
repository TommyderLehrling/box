# FRAGEN_L13 — Fragen und Erkenntnisse (Box, Stand 10.10.2026)

Alles ist Entwurf, bis VSC es im Browser fährt. Antworten bitte in die Spalte „Antwort“.

| Nr. | Punkt | Entscheidung / Frage | Antwort |
|---|---|---|---|
| 1 | **Startstandort Pflicht und Büro/Einkauf** | Der Startstandort braucht `buchen` auf der Kostenstelle. `buero` und `einkauf` haben `pflegen`, aber kein `buchen`: ihre Wahl bleibt leer, sie können über die Oberfläche **kein** Stück mehr anlegen (vorher legten sie Stücke ohne Standort an, die nur der Verwalter sah). Vorschlag: beim Anlegen genügt `pflegen`, wenn die Kostenstelle für den Benutzer erlaubt ist — oder den Vorlagen `buero`/`einkauf` `buchen` geben. Was gilt? | |
| 2 | „Dialog“ je Zeile | Die Taste „Prüfung eintragen“ der Fällig-Liste springt auf die Stück-Seite und öffnet dort den Dialog mit der Prüfart (danach zurück auf die Liste). Grund: ein Lieferanten-Suchfeld statt hunderte auf einer Seite | |
| 3 | Kaufdaten im Import | Ohne `kosten_pflegen` ignoriert der Import Kaufpreis und -datum der Datei (kein Fehler, auch nicht als Abweichung). Besser abweisen oder so lassen? | |
| 4 | Zählerstand aus der Prüfung | Er wird zusätzlich als Ablesung (Quelle `pruefung`) geführt, wenn er nicht unter dem letzten Stand liegt; sonst bleibt er nur an der Prüfung | |
| 5 | Prüfer | Ein Name geht vor dem gewählten Benutzer. Intern ohne Angabe = der Eintragende. Extern verlangt Lieferant oder Name | |
| 6 | Nachweis | PDF, JPG, PNG bis 10 MB; es zählt der Dateianfang, die Endung kommt vom Inhalt. Abruf `/inventar/pruefung/<id>/nachweis` (Recht `sehen` am Stück) prüft die SHA-256 und liefert als Anhang | |
| 7 | Prüfarten pflegen | Je Gruppe in „Verwaltung › Prüfarten“ (Recht `einstellen`), je Stück an der Stück-Seite (Recht `pflegen`). Nichts wird gelöscht: abschalten setzt `aktiv` aus | |
| 8 | Erinnerung Prüfungen | Mail an `werkstatt` nur bei **neuen** Fälligkeiten und montags mit allen Überfälligen; „bald“ = gelb und höchstens `pruefung_erinnern_tage` (Standard 14) Tage. Gemerkt wird in `einstellung` (`erinnern_pruefung_gesehen`, kurze Kennungen). Passt der Rhythmus? | |
| 9 | Kachel „Prüfungen fällig“ | Sie braucht weiter `pruefen`; ein Konto nur mit `werkstatt` sieht sie nicht, bekommt aber die Mail. Soll die Kachel auch für `werkstatt` gelten? | |
| 10 | Prozess-Takt | `erinnern` prüft alle 5 Minuten (ein Log-Satz `zugriff.einzelmandant`), nach erledigtem Tag bis zum nächsten Datum nicht mehr. Der Lauf kann bis zu 5 Minuten nach `erinnern_um` beginnen | |
| 11 | `start.py` | Dass der Kern den Prozess über `prozesse` startet und überwacht, habe ich nur gegen den Steckbrief gebaut; von Hand gestartet und mit SIGTERM beendet. Bitte im Container prüfen | |
| 12 | Einstellungen | Neu: `erinnern_um`, `pruefung_erinnern_tage` (T-I-5 zählt jetzt 10 statt 8 Einstellungen) | |
| 13 | Nicht gebaut | Werkstatt (L14), Kosten (L15), Playwright-Dateien (L16) | |
