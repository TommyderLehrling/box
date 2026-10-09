# Integrationsläufe des Inventars — wie man sie startet

Jeder Lauf braucht **seinen** Aufbau und steht darum nicht im gewöhnlichen Lauf (`pytest.ini`: `norecursedirs`). Steht der
falsche Aufbau da, wird die Datei rot (`aufbau_pruefen`), nie übersprungen. Prüfdatenbank: `<db>_test` des Servers —
**nie zwei Läufe gleichzeitig** auf demselben Server.

| Lauf | Aufbau | Datei |
|---|---|---|
| **T-I-5** | Kern + Inventar | `tests/integration/test_t_i_5.py` |
| **T-I-6**, T-K-14 | Kern + Belegerfassung + Inventar | `tests/integration/test_t_i_6.py` |

## Ohne Docker (Anleitung VSC `LAUFEN_OHNE_DOCKER.md`, geprüft auf PostgreSQL 16, Konto Superuser)

```
python3.12 -m venv v && . v/bin/activate
pip install -r requirements.txt                       # die des Kerns, dazu openpyxl, weasyprint
pip install --no-deps digiassistenz_kern-0.15.2-py3-none-any.whl
pip install --no-deps -e <pfad>/Inventar              # Einstiegspunkt digiassistenz.module → inventar
cd <wurzel mit konfig.env>                            # ARBEITSORDNER, DB_URL, MANDANT_NAME, WEB_GEHEIMNIS
DIGIASSISTENZ_WURZEL=$PWD python -m pytest <pfad>/Inventar/tests/integration/test_t_i_5.py
```

* PostgreSQL 16 **mit contrib** (`pg_trgm`) und `pg_dump` 16 im `PATH`, sonst migriert der Kern nicht.
* Nicht aus einem Ordner starten, über dem die `pyproject.toml` des Kern-Repositorys liegt.
* `python -m pytest`, nicht `pytest`. Immer die Zeile `passed/failed/skipped` lesen: `skipped` muss 0 sein.

## Mit Docker

`docker compose -f compose.yml up -d` im Ordner des Inventars (siehe `INTEGRATION_VSC.md`); die Läufe dann im Container:

```
docker compose run --rm -T app sh -c 'pip install --no-deps -e /kern -e /projekt; cd /projekt && python -m pytest tests/integration/test_t_i_5.py'
```

T-I-6 läuft im Bild der Belegerfassung, in das das Inventar zusätzlich eingebaut wird (wie T-I-4 mit der Attrappe).
