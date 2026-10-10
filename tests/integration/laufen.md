# Integrationsläufe des Inventars — wie man sie startet

Jeder Lauf braucht **seinen** Aufbau und steht darum nicht im gewöhnlichen Lauf (`pytest.ini`: `norecursedirs`). Steht der
falsche Aufbau da, wird die Datei rot (`aufbau_pruefen`), nie übersprungen. Prüfdatenbank: `<db>_test` des Servers —
**nie zwei Läufe gleichzeitig** auf demselben Server.

| Lauf | Aufbau | Datei |
|---|---|---|
| **T-I-5** | Kern + Inventar | `tests/integration/test_t_i_5.py` |
| Seiten L11–L13, Anwendungsfälle, Modelle gegen Kette | Kern + Inventar | `test_seiten_db.py`, `test_pruefungen_db.py`, `test_dienstlogik_db.py`, `test_migration_gegen_modelle.py` |
| **T-I-6**, T-K-14 | Kern + Belegerfassung + Inventar | `tests/integration/test_t_i_6.py` |

## Ohne Docker (Anleitung VSC `LAUFEN_OHNE_DOCKER.md`, geprüft auf PostgreSQL 16; Superuser, und seit dem Nachtrag 10.10. auch Nicht-Superuser)

```
python3.12 -m venv v && . v/bin/activate
pip install -r requirements.txt                       # die des Kerns, dazu openpyxl, weasyprint
pip install --no-deps digiassistenz_kern-0.15.3-py3-none-any.whl
pip install --no-deps -e <pfad>/Inventar              # Einstiegspunkt digiassistenz.module → inventar
cd <wurzel mit konfig.env>                            # ARBEITSORDNER, DB_URL, MANDANT_NAME, WEB_GEHEIMNIS
DIGIASSISTENZ_WURZEL=$PWD python -m pytest <pfad>/Inventar/tests/integration/test_t_i_5.py
```

* PostgreSQL 16 **mit contrib** (`pg_trgm`) und `pg_dump` 16 im `PATH`, sonst migriert der Kern nicht.
* **Nicht-Superuser** (Nachtrag `LAUFEN_OHNE_DOCKER.md`, von GER gefahren): ein Konto `LOGIN CREATEDB CREATEROLE` als Eigentümer der Datenbank
  geht, wenn **dasselbe Konto** die Rollen `kern_nutzer`, `app_probe` und `inventar_nutzer` selbst anlegt (ein Konto für alle Ketten).
  Rot wird es, wenn ein anderes Konto (z. B. ein Superuser) die Rollen vorher angelegt hat: `permission denied to grant role` —
  PostgreSQL 16 gibt `ADMIN OPTION` nur dem Ersteller. Dann entweder alle Ketten mit **einem** Konto fahren oder als Superuser
  `GRANT <rolle> TO <konto> WITH ADMIN OPTION` je Rolle (`kern_nutzer`, `app_probe`, `inventar_nutzer`).
* Nicht aus einem Ordner starten, über dem die `pyproject.toml` des Kern-Repositorys liegt.
* `python -m pytest`, nicht `pytest`. Aus der Wurzel mit `konfig.env` braucht der Aufruf `--rootdir=<Ordner des Inventars>`. Immer die Zeile `passed/failed/skipped` lesen: `skipped` muss 0 sein.

## Mit Docker

`docker compose -f compose.yml up -d` im Ordner des Inventars (siehe `INTEGRATION_VSC.md`); die Läufe dann im Container:

```
docker compose run --rm -T app sh -c 'pip install --no-deps -e /kern -e /projekt; cd /projekt && python -m pytest tests/integration/test_t_i_5.py'
```

T-I-6 läuft im Bild der Belegerfassung, in das das Inventar zusätzlich eingebaut wird (wie T-I-4 mit der Attrappe).
