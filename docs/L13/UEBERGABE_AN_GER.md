# Übergabe an GER — Auftrag 04 (Abschnitt 1–4) und Lieferung L13

Von: Box. Stand: 10.10.2026. Ansprechpartner für alles aus dieser Lieferung ist GER. Box gibt nichts direkt an VSC, CD oder Thomas weiter.
Alles ist Entwurf, bis VSC es auf dem echten Kern (0.15.3) fährt.

## 1. Was fertig ist

| Teil | Stand |
|---|---|
| Abschnitt 1: Umstellung auf Kern 0.15.3 (`kern_mindestens`, `prozesse`, `required` an Pflicht-Wahlen) | fertig |
| Abschnitt 2: Antworten zu L10–L12 umgesetzt | fertig |
| Abschnitt 3: Erinnerungen als Modulprozess `python -m digiassistenz_inventar.erinnern` | fertig, nur von Hand gestartet |
| Abschnitt 4: Pakete, Systempakete, Nicht-Superuser-Satz | als Anleitung und `docker/Dockerfile` (nicht gebaut) |
| L13: Fällig-Liste, Prüfung mit Nachweis, Prüfarten je Gruppe/Stück, Erinnerung an `werkstatt` | fertig |

Tests: `python -m pytest -q -W error` 317 passed, Integration (ohne T-I-6) 36 passed, jeweils `skipped = 0` (Kern 0.15.3, PostgreSQL 16.15).

## 2. Wo alles liegt

| Was | Git (Repo `tommyderlehrling/box`, Branch `claude/inventar-modul-vorarbeit-oil35n`, Commit `4dfb80f`) | Drive |
|---|---|---|
| Code des Moduls | `digiassistenz_inventar/` | `Gerate-App/box/lieferungen/L13/Inventar/…` |
| Texte | `digiassistenz_inventar/texte/de.json` | Unterordner `texte` |
| Tests | `tests/`, `tests/rein/`, `tests/integration/` | Unterordner `tests` |
| Anleitung für VSC | `INTEGRATION_VSC.md` | in der Lieferung |
| Aufruf der Integrationsläufe | `tests/integration/laufen.md` | Unterordner `tests/integration` |
| Fragen mit Antwortspalte | `docs/L13/FRAGEN_L13.md` | in der Lieferung |
| Protokoll | `docs/PROTOKOLL_BOX_07.md` | in der Lieferung |
| Diese Übergabe | `docs/L13/UEBERGABE_AN_GER.md` | neben `FRAGEN_L13.md` |

## 3. Welche Datei soll wohin (Vorschlag von Box, GER entscheidet)

| Datei | Soll zu | Wozu |
|---|---|---|
| `INTEGRATION_VSC.md`, `tests/integration/laufen.md`, Repo und Branch | VSC | Modul auf dem echten Kern fahren; Hinweise zu Docker, Kern-Start und Browserfällen stehen darin |
| `FRAGEN_L13.md` | GER zuerst | GER beantwortet, was er selbst entscheiden kann, und trägt die Antwort in die Spalte „Antwort“ ein. Was nicht GER gehört, gibt er weiter. Box weiß nicht, wer das ist, und rät nicht. |
| `PROTOKOLL_BOX_07.md` | GER | Nachweis, was geprüft wurde und was nicht |
| `texte/de.json` und Tests | gehen mit dem Repo; müssen nicht einzeln verteilt werden | |

## 4. Was GER entscheiden oder weitergeben muss

1. **FRAGEN Nr. 1 (dringend):** Büro und Einkauf können über die Oberfläche keine Stücke mehr anlegen, weil der Startstandort Pflicht ist und `buchen` auf der Kostenstelle verlangt, beide Vorlagen aber nur `pflegen` haben. Vorschlag A: beim Anlegen genügt `pflegen`, wenn die Kostenstelle für den Benutzer erlaubt ist. Vorschlag B: den Vorlagen `buero` und `einkauf` das Recht `buchen` geben. Box setzt um, was GER festlegt.
2. **FRAGEN Nr. 2–10:** Entscheidungen zum Verhalten (Dialog an der Stück-Seite, Kaufdaten im Import, Zählerstand aus der Prüfung, Prüfer, Nachweis, Erinnerungsrhythmus, Kachel, Prozess-Takt). Jede hat in der Tabelle eine Spalte für die Antwort.
3. **FRAGEN Nr. 11:** Dass der Kern den Prozess über `prozesse` startet und überwacht, ist nur gegen den Steckbrief gebaut. Das muss VSC im Container prüfen.
4. **Freigabe L14–L16** (Werkstatt, Kosten, Playwright-Dateien): Box baut sie erst auf Freigabe.

## 5. Was nicht geprüft ist

Docker-Bild und Compose, Kern-Start mit `prozesse` im Container, Browser, Kamera und Druck, T-I-6 mit Belegerfassung (VSC hat es mit 0.15.3 gefahren: 3 passed; Box nicht).

## 6. Guthaben

Nach L13 verbleiben Box rund 14,6 Mio. Tokens.
