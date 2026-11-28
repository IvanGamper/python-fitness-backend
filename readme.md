# Python Fitness Backend

## Shop-API und ERP-Import

FastAPI stellt die beiden PDF-Trainingspläne unter `GET /api/v1/products` als
Beispieldaten bereit. Das Importskript ruft die API per HTTP ab, validiert den
gesamten Katalog und schreibt die Artikel in ein lokales Demo-ERP (SQLite).
Die Daten stammen aus `shop_catalog.py`. Die öffentliche Programmseite und
ihre PayPal-Zahlung sind von der Demo unabhängig.

Im Backend-Ordner die Python-Umgebung aktivieren. Wenn darin noch Pakete
fehlen, zuerst `python -m pip install -r requirements.txt` ausführen.
Für einen rein lokalen Test der Produkt-API reicht ein Platzhalter in der
beim Backend-Start benötigten Resend-Variable.

```powershell
$env:RESEND_API_KEY = "local-demo"
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

In einem zweiten Terminal im Backend-Ordner lässt sich erst die HTTP-Antwort
ansehen und dann derselbe Import zweimal starten.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/products | ConvertTo-Json -Depth 4
python erp_sync.py --db "$env:TEMP\pf-erp-demo.sqlite3"
python erp_sync.py --db "$env:TEMP\pf-erp-demo.sqlite3"
```

Bei einer frischen Datenbank meldet der erste Lauf zwei neue Artikel, der
zweite zwei unveränderte. Die `sku` aus dem Shop ist im ERP die
`artikelnummer`. Preise werden als ganze Centbeträge gespeichert. Ändert sich
ein Preis, wird der vorhandene Artikel anhand seiner Artikelnummer
aktualisiert. Fehlt ein Artikel im Katalog, bleibt sein ERP-Eintrag erhalten.
Bei einer ungültigen API-Antwort stoppt der Import vor dem Schreiben.

Mit `--url` lässt sich eine andere API-Adresse angeben. Das Schema steht im
lokal gestarteten Backend unter [FastAPI-Dokumentation](http://127.0.0.1:8000/docs).

## Beide Übungsdienste mit Docker Compose starten

Starte Docker und führe im Backend-Ordner diesen Befehl aus:

```powershell
docker compose up --build
```

- [Produktkatalog](http://127.0.0.1:8100/api/v1/products)
- [Bestell-API in Swagger](http://127.0.0.1:8101/docs)

Bei `POST /orders` zum Beispiel die Bestellnummer `DOCKER-001`, die SKU
`PF-SHOULDER-MOBILITY` und die Menge `1` senden. Der Bestellservice erreicht
den Produktdienst intern über `http://products:8000/api/v1/products`. Seine
SQLite-Datei liegt im Docker-Volume `orders-data`. So stehen die Bestellungen
auch nach `docker compose down` und einem erneuten Start zur Verfügung.
