# Fragen zu L8 (keine blockiert)

1. **Kachel „Meldungen offen"** zählt nur Status `offen` (noch niemand angenommen). Gewollt, oder auch `angenommen`?
2. **Kachel „fällig/überfällig"** zählt Prüfarten je Stück (rot und gelb), nicht Stücke. Passt das?
3. **„Angekündigt an mich"** geht über die Kostenstellen der Person (`meine_kostenstellen`). Hat VSC dafür die Zuordnung der Sitzung, oder soll die Funktion die Person kennen?
4. **Weg-Schlüssel** (`inventar.faellig`, `inventar.hier`, `inventar.uebersicht`, `inventar.werkstatt`) sind meine Namen; bitte durch die echten Wege ersetzen.
5. **Miete gegen eigen:** Vergleich mit dem Mittelwert der eigenen Tagessätze in der Gruppe (Spec: „eines eigenen Stücks"). Besser das teuerste, das günstigste oder ein bestimmtes Stück?
6. **Standardwerte:** bitte Thomas die Zahlen prüfen lassen; ich habe 4 % Zins für alle angesetzt.
7. **Scan-Zeichen:** ein `%` im getippten Text wird abgelehnt (Verdacht auf kaputte Kodierung). Gibt es Nummernmuster mit Sonderzeichen außer `- _ . / Leerzeichen`?
8. **Standard-Änderung** `mit_menge=True`: bestehende Aufrufer mit `mit_menge=True` bleiben gleich, Aufrufer ohne Angabe rechnen jetzt mit Menge.
