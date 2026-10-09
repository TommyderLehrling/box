#!/usr/bin/env bash
# Start des Containers mit Kern + Inventar (Muster: docker/app-start.sh des Kerns und compose.attrappe.yml).
#
# Der Kern kommt als Wheel, das Inventar wird per `pip install -e` eingebaut (nur Metadaten, --no-deps); dann startet
# `digiassistenz_kern.start`: Ketten (Kern zuerst, dann i0001), Startdaten, der Webserver und die `prozesse` der Module.
set -euo pipefail

pip install --quiet --root-user-action=ignore --no-deps /wheels/digiassistenz_kern-*.whl
pip install --quiet --root-user-action=ignore --no-deps -e /inventar

exec python -m digiassistenz_kern.start
