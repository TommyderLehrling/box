# DOKON Inventar — Bild für Kern + Inventar (L10, Entwurf; Box hat es nicht gebaut — VSC prüft).
#
# Rezept: das Bild des Kerns (`digi-assistenz-kern`, Dockerfile im Kern-Repository: python:3.12-slim-bookworm,
# postgresql-client-16 für pg_dump, die festen Pakete aus requirements.txt, setuptools) plus
#   * die Systempakete für WeasyPrint (libpango, libcairo, Schrift) — Etiketten-PDF,
#   * openpyxl und weasyprint (segno und alles andere bringt der Kern mit).
# Der Kern selbst reist als Wheel (docker/wheels/, Tag kern-x.y.z), das Inventar wird beim Start eingebaut.
#
# Zu prüfen (VSC): KERN_BILD trifft das gebaute Kern-Bild; die Paketnamen der Schriften auf bookworm;
# `python -c "from weasyprint import HTML; HTML(string='x').write_pdf()"` im Bild.
ARG KERN_BILD=digi-assistenz-kern:0.2.0
FROM ${KERN_BILD}

RUN apt-get update && apt-get install --no-install-recommends -y \
        libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libharfbuzz0b shared-mime-info fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-modul.txt /opt/digiassistenz/requirements-modul.txt
RUN pip install --requirement /opt/digiassistenz/requirements-modul.txt

COPY docker/app-start.sh /opt/digiassistenz/app-start.sh
WORKDIR /inventar
CMD ["bash", "/opt/digiassistenz/app-start.sh"]
