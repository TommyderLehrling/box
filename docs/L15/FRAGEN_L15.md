# FRAGEN_L15 — Fragen und Erkenntnisse (Box, Stand 11.10.2026)

Alles ist Entwurf, bis VSC es im Browser fährt. Antworten bitte in die Spalte „Antwort“. Gilt für L14a (Nr. 1–6) und L15 Kosten (Nr. 7–22).

| Nr. | Punkt | Entscheidung / Frage | Antwort |
|---|---|---|---|
| 1 | Mail an Person: Form | `benachrichtigen(db, benutzer, schluessel, *, mandant_id, von=None, objekt_id=None, **felder)` in `dienstlogik/benachrichtigen.py`. `mandant_id` ist ein Pflicht-Schlüsselwort (ohne es: `TypeError`), `von` die handelnde Person, `objekt_id` das Stück, an dessen Verlauf der Vermerk gehört. Betreff und Text stehen unter `inventar.mail.<schluessel>.betreff/.text`. Passt die Form, oder soll `mandant_id` aus einer Sitzung kommen? | |
| 2 | Eine Mail je Person | `erinnerungen.py` schickt jetzt **eine Mail je Person** (vorher eine Mail an alle Empfänger zugleich). Mit Block V kommt die Kern-Meldung je Person an derselben Stelle dazu. Heißt das auch: kein gemeinsames `an=[…]` mehr? | |
| 3 | Vermerke bei Fehlern | Ohne aktives Konto oder ohne Adresse: kein Einreihen, Protokollvermerk `inventar.mail_ohne_adresse` (am Stück, wenn es eines gibt). Scheitert das Einreihen (Ausnahme): Teiltransaktion zurück, Vermerk `inventar.mail_nicht_eingereiht`, die Handlung gilt. Genügt der Vermerk im Verlauf des Stücks, oder soll die Werkstatt-Seite es auch zeigen? | |
| 4 | Haken bei offener Meldung | Ist die Meldung noch `offen`, geht der Haken „Meldung damit erledigen“ über `angenommen` nach `erledigt` (zwei Vermerke im Verlauf, ein Mailtext). Die Automaten bleiben unverändert (offen → erledigt gibt es dort nicht). Gewollt? Eine **zurückgezogene** Meldung bekommt den Haken nicht. | |
| 5 | Rückmeldung „vorgefüllt mit `arbeit`“ | Vorfüllen braucht eine Zeile Skript (`statisch/inventar.js`: die Rückmeldung folgt dem Feld „Was gemacht wurde“, solange niemand sie selbst ändert). Ohne Skript gilt serverseitig dasselbe: leere Rückmeldung = `arbeit`. Im Browser nicht gefahren. | |
| 6 | Abschluss-Dialog | Der Abschluss öffnet einen **Dialog oben** auf der Werkstatt-Seite (`?abschluss=<id>`), nicht mehr je Zeile — wegen des Firmenfelds (ein Suchfeld statt eines je Zeile). Für die Person (intern) eine Auswahl aller aktiven Konten des Betriebs, vorbelegt mit der Abschließenden. Passt das so? | |
| 7 | Extern ohne Firma beim Anlegen | Beim Anlegen bleibt alles freiwillig (auch die Firma bei „extern“); beim Abschließen ist sie Pflicht, wahlweise dort nachzutragen. Reparaturen, die schon vor L14a ohne `arbeit` abgeschlossen wurden (`i0001` ist noch offen), tragen `arbeit = ''`. | |
| 8 | Foto am Stück | `/inventar/stueck/<id>/foto` zeigt das **neueste** Foto (Spalte `foto_pfad`); ältere Dateien liegen im Ordner, haben aber keinen Abruf. Genügt das? | |
| 9 | Hand bleibt Hand: Altfall | Ein schon vor L14a automatisch gesetztes `in_reparatur` hat keinen Grund `reparatur:<id>` und bleibt darum stehen, bis die Werkstatt es aufhebt (nur ein Altfall, `i0001` ist noch offen). | |
| 10 | Rechte der Gruppen-Kostensätze | Verwaltung → Kostensätze verlangt weiter **`kosten_pflegen`** (so seit L8), der Auftrag nennt bei der Gruppe `einstellen`. Welches gilt? Der Verwalter hat beide; `einkauf` und `buchhaltung` haben nur `kosten_pflegen`. | |
| 11 | Wirksamer Satz | Je Stück gilt die **eigene** Zeile (jüngster Beginn bis heute), sonst die der Gruppe, sonst die der übergeordneten Gruppe. Parameter: Kaufpreis (des Stücks; die Kaufpreisbasis nur, wenn es keinen hat), Nutzungsdauer, Restwert (Betrag oder Prozent), Zins 4 %, Reparaturanteil/Jahr. Gerechnet wird **bei jedem Lesen** (nichts Abgeleitetes in der Datenbank); nur ein von Hand gesetzter Monatssatz steht als Zahl in der Zeile. „Gerechnet am“ in der Verwaltung ist `angelegt_am` der Zeile. Passt das? | |
| 12 | Quelle `gerechnet` / `manuell` / `bgl` | Eine Zeile ohne Monatssatz ist `gerechnet` (bisher immer `manuell`), mit Monatssatz `manuell`. `bgl` setzt niemand in der Oberfläche — das wäre ein Einspielen aus der Baugeräteliste (nicht gebaut). Tages- und Wochensatz von Hand brauchen den Monatssatz. | |
| 13 | Kalendertage / Werktage | Standard: Kalendertage mit `tage_je_monat` (30). Steht `werktage` > 0 (jetzt auch mit Komma, z. B. 21,67), rechnet **alles** nach Werktagen (Mo–Fr): der Tagessatz durch diese Zahl, die Vorhaltung mit Werktagen. **Feiertage** kennt das Modul nicht — es zählt Mo–Fr (`feiertage=()`). Kommt eine Feiertagsliste (Kern oder Einstellung)? | |
| 14 | Vorhaltung und Zeitzone | Die Tage zählen in **Ortszeit** (Standortzeiten werden vor dem Rechnen umgerechnet), Eingangstag zählt zum Ziel, Abgangstag nicht zur Quelle. Teil-Eingang: Was unterwegs ist, steht nirgends vor Ort und kostet nichts; die vier, die der Automat nach dem Teil-Eingang wieder bei A führt, zählen bei A. Stimmt das fachlich? | |
| 15 | „Gesamtkosten“ je Stück | Kaufpreis + alle Reparaturkosten (belegt und geschätzt, `rein.gesamtkosten`). „Kalkulatorische Kosten bis heute“ (Monate seit Kauf × Monatssatz, höchstens die Nutzungsdauer) steht daneben und ist **nicht** in der Summe, weil der Monatssatz den Reparaturanteil schon enthält. Gewollt? | |
| 16 | Miete gegen eigen | Mietkosten, Beginn und Ende trägt `kosten_pflegen` an der Stück-Seite ein (Abschnitt Kosten). Verglichen wird mit dem **mittleren** Tagessatz der eigenen Stücke derselben Gruppe oder — mit `vergleich=<Nummer>` — mit einem bestimmten. Mietstücke ohne Zeitraum oder Kosten fehlen und werden gezählt. | |
| 17 | CSV-Auszüge | Vier Blöcke (je Kostenstelle, je Stück, Miete, Anlagenbuch) nach `inventar/<mandant>/export/kosten_<block>_<JJJJMMTT-HHMMSS>.csv` (UTF-8 mit BOM, Semikolon, Dezimalkomma); die Seite listet die Pfade, **lädt aber nichts herunter**. Soll ein Abruf (Download) dazu? Das Anlagenbuch ist der Auszug der Kaufdaten; eine eigene „Erweiterungsstelle“ des Kerns dafür gibt es im Steckbrief 0.15.4 nicht — ich habe keine erfunden. | |
| 18 | Einsatzstunden / Rechnungen | Nicht in L15 (Dienste `maschinenstunden`, `rechnungen_zu_stueck`, AP-K2): die Spalte `satz_stunde` wird gespeichert, aber nirgends gerechnet. | |
| 19 | Zählerstände | Quellen im Verlauf: Eingabe, Prüfung, Werkstatt (neu: Feld beim Abschließen einer Reparatur an Großgeräten, mit Hinweis bei zu niedrigem Stand), Import (kennt die Vorlage nicht — keine Spalte), Baustelle (erst mit dem Dienst). Ein zu niedriger Stand wird bei der Eingabe an der Stück-Seite weiter **abgelehnt** (Fehlersatz), in Prüfung und Werkstatt nur **vermerkt**. | |
| 20 | Inventur: wer darf | Die Seite öffnet für **`stilllegen` oder `einstellen`**; den Stichtag setzt nur `einstellen`, „als vermisst eintragen“ braucht `stilllegen` (der Statuswechsel nach `vermisst` hat dieses Recht seit L7). Die Kachel in der Verwaltung folgt `stilllegen`; die Verwaltungs-Startseite selbst öffnet weiter nur für `einstellen` oder `pflegen`. Passt das, oder soll es ein eigenes Recht sein? | |
| 21 | Inventur: „gesehen“ | Gesehen = seit dem Stichtag (0:00 Ortszeit) „Ist hier“ gescannt auf der Kostenstelle, auf der das Stück schon stand (Protokollzeile `inventar.inventur_gesehen`, jetzt mit dem Ort in `alt_wert`), oder dort per Eingang bestätigt. Beim Mengenartikel zählt ein Scan als **vollständig gesehen** (der Scan nennt keine Menge); ein Teil-Eingang zählt seine Menge. Fehlmengen werden gezeigt, nicht gebucht. Stimmt das? | |
| 22 | Nicht gefahren / gebaut | Nicht gefahren: Docker-Bild, Browser, Kamera, Druck, T-I-6, der Prozess `erinnern` im Container (diesmal nur die Fälle im Test). Nicht gebaut: Playwright-Dateien (L16), Etikett-Code (Abschnitt 7 vorgesehen), Einsatzstunden, Rechnungen, steuerliche AfA, Feiertage, Download der Auszüge, BGL-Einspielen. | |


## Antworten GER (11.10.2026 — Fach-Entscheidungen von Thomas; **Vorab-Fassung:** CD und VSC lesen in Umlauf 04 noch gegen. Was von ihnen abhängt, ist markiert ⏳; alles andere gilt)
| Nr. | Antwort |
|---|---|
| 1 | **Ja, Form passt.** `mandant_id` bleibt Pflicht-Schlüsselwort (der `TypeError` ohne es ist gewollt) — nicht aus einer Sitzung ziehen, der Prozess `erinnern` hat keine Benutzersitzung |
| 2 | **Ja** — eine Mail je Person, kein gemeinsames `an=[…]` mehr ⏳ (CD nickt in Umlauf 04) |
| 3 | **Vermerk im Verlauf genügt.** Zusatz (L15a): die Werkstatt-Seite zeigt am Vorgang ein kleines „✉ nicht zugestellt (keine Adresse)", wenn der letzte Vermerk `mail_ohne_adresse`/`mail_nicht_eingereiht` ist |
| 4 | **Ja, gewollt** (`offen` → `angenommen` → `erledigt`, zwei Vermerke, ein Mailtext); zurückgezogene ohne Haken: ja |
| 5 | **Ja**; VSC fährt das Skript im Browser (ein Playwright-Fall in L16) |
| 6 | **Ja.** Auswahl der Person (L15a): zuerst Konten mit Baustein `inventar.werkstatt`, dann die übrigen aktiven — wenn das mit einer Abfrage geht; sonst alle aktiven |
| 7 | **Ja** |
| 8 | **Ja, genügt** für jetzt; eine Liste älterer Bilder kommt später (nicht L16) |
| 9 | **Ja** |
| 10 | **`kosten_pflegen` gilt** (Thomas) — Einkauf und Buchhaltung pflegen die Sätze; der Auftrag 06 war ungenau, du hast richtig gebaut |
| 11 | **Ja.** Beschriftung (L15a): „Stand der Parameter" statt „Gerechnet am" |
| 12 | **Ja**; `bgl` bleibt reserviert |
| 13 | **Ja, bauen (Thomas, L16):** Einstellung je Mandant „Bundesland" (16 Länder); gesetzliche Feiertage rechnet das Modul in `rein/feiertage.py` (feste + bewegliche nach Ostern; Prüffälle mit Sollwerten 2026/2027, je Land), dazu eigene Tage je Jahr eintragbar (Verwaltung → Einstellungen). Werktage = Mo–Fr ohne Feiertage des Bundeslands; der `werktage`-Teiler bleibt Einstellung. **Datenzugriff an einer Stelle** (`dienstlogik/feiertage.py`), damit die Liste später in den Kern wandern kann ⏳ (CD sagt in Umlauf 04, ob der Kern sie will — baue so oder so im Modul) |
| 14 | **Ja, fachlich richtig** (Thomas): Ortszeit, Eingangstag zum Ziel, Abgangstag nicht zur Quelle, unterwegs kostet niemanden, Teil-Eingang wie gebaut |
| 15 | **Ja (Thomas):** echt und kalkulatorisch getrennt, nicht addiert. Dazu (L15a) eine **Vergleichszeile** „Reparaturen: geplant (Monate seit Kauf × Reparaturanteil je Monat) / angefallen (Σ `reparatur.kosten`)" auf der Stück-Seite und im Block je Stück; Beschriftung „echt" / „kalkulatorisch" |
| 16 | **Ja** |
| 17 | **Download dazu (Thomas, L15a):** `/inventar/kosten/auszug/<dateiname>` mit `kosten_sehen`, nur Dateien aus `export/` (Pfadprüfung wie beim Nachweis), `Content-Disposition: attachment`, `nosniff`; die Datei bleibt zusätzlich im Ordner. **Keine Erweiterungsstelle** — richtig, nichts erfinden ⏳ (CD bestätigt) |
| 18 | **Ja** (bis Dienst `maschinenstunden`, AP-K2) |
| 19 | **Ja.** Dazu (L16): Spalte „Zählerstand" in die Excel-Importvorlage (Quelle `import`, Plausibilität wie Prüfung: zu niedrig → nur vermerkt) |
| 20 | **Ja, so** (Thomas) — kein eigenes Recht |
| 21 | **Ja — mit einer Änderung (Thomas, L16):** beim Scan eines **Mengenartikels während einer laufenden Inventur** fragt die Hier-Seite die **Menge** ab (vorbelegt mit der Buchmenge); gesehen = genannte Menge, Fehlmenge = Rest, nichts wird gebucht |
| 22 | T-I-6 fährt VSC mit dem Kern-Tausch; Docker/Browser/Kamera/Druck bei VSC/Thomas. **L16 ist freigegeben (Thomas, 11.10.)** — Inhalt in `BOX_AUFTRAG_07.md` |

**Dazu:** Kern bleibt 0.15.4 · die ungenutzten Importe (pyflakes) räumst du mit L16 auf · deine flache Lieferform mit Sortiertabelle hat funktioniert (48/48) — so weiter.
