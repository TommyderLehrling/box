# Fragen zu L7 (keine blockiert)

1. **Reihenfolge der Ampel im Gesamtstand:** rot > gelb > unbekannt > grün. Soll „kein Nachweis" schlimmer sein als „bald fällig"? (Angenommen: nein, weil gelb eine Handlung in 30 Tagen verlangt.)
2. **Fehlmenge:** Sie übernimmt `abgang_am` des Ursprungs, ist also sofort so alt wie der Abgang und erscheint früh in den Überfälligen. Gewollt, oder soll die Frist mit dem Teil-Eingang neu beginnen?
3. **Überholen mit Teilmenge:** Ein Scan mit abweichender Menge an einem dritten Ort bleibt `transfer.menge_abweichend`. Soll dort auch ein Teil-Eingang möglich sein?
4. **Neues Feld `Transfer.eingang_schluessel`** (Idempotenz beim erneuten Scan, siehe README). VSC muss es speichern. Einverstanden?
5. **Breaking:** `pruefstand` hat keine Parameter `ab` und `erstfaellig` mehr; Prüfart `dguv_v3` heißt nun `dguv_v3_baustelle`/`dguv_v3_buero` — bestehende Zuordnungen und Einträge muss VSC migrieren.
6. **HU:** Standard 12 Monate gilt für alle Fahrzeuge; PKW (24) müssen je Stück überschrieben werden. Soll `fahrzeugklasse` das Intervall automatisch vorgeben? Dann bräuchte ich eine Regel „Merkmalswert → Intervall".
7. **Fachlich nicht geprüft:** alle Fristen und Rechtsgründe der Prüfarten (Richtwerte aus Auftrag 02, „(prüfen)" bleibt).
8. **Weiterhin offen:** Etikettenbogen (Thomas), Kostenstellen-Liste in der Vorlage.
