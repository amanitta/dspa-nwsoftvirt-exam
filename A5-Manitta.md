# A5 — Frontend + API + DB (3-tier)

**Studente:** Andrea Manitta
**Famiglia:** A — Docker Compose multi-container

> Riferimenti comuni a tutti i progettini: `../Progettini_Istruzioni_Operative.md`.

## 1. Obiettivo formativo

Capire l'architettura **3-tier** classica e, soprattutto, capire perché si segmenta la rete in **due reti Docker distinte** invece che metterle tutte sulla stessa: si vuole che il DB **non sia mai raggiungibile** dal frontend, e che il frontend non possa "saltare" l'API. È l'esempio più pulito per toccare con mano la **segmentazione di rete a livello di container**.

In secondo piano: imparare come si serve un sito statico via nginx in container, come l'API parla solo con il DB sulla rete interna, e come i tre tier si "vedono" o "non si vedono" in modo controllato.

## 2. Cosa costruire (architettura attesa)

Tre servizi e **due reti Docker** distinte (entrambe interne alla composizione):

- **`frontend`** (nginx): serve un piccolo sito statico HTML/JS che, da browser, fa `fetch` verso l'API. È sulla rete `frontend-net`. Espone porta `80` sull'host (es. `8080:80`).
- **`api`**: web app Python (Flask/FastAPI) con endpoint REST (es. `GET /api/items`, `POST /api/items`). È **su entrambe le reti**: `frontend-net` (per ricevere chiamate dal frontend) e `db-net` (per parlare con il DB). Non espone direttamente porte sull'host (oppure le espone solo per debug, da discutere).
- **`db`** (Postgres 16): **solo** sulla rete `db-net`. Volume nominato per la persistenza.

Schema della topologia attesa (da riprodurre in ASCII art nel `README`):

```
host
 │
 │ :8080
 ▼
[frontend nginx] ── frontend-net ── [api]
                                      │
                                      └── db-net ── [db postgres]
```

## 3. Tecnologie consigliate

- **nginx:alpine** per il frontend.
- **Python 3.11+** con Flask o FastAPI per l'API. CORS configurato per il frontend.
- **Postgres 16-alpine** per il DB, con volume nominato.
- Due **named networks** Compose: `frontend-net` e `db-net`.
- Variabili d'ambiente per la connection string del DB; CORS origin = `http://localhost:8080`.

> **Nota — alternative DB ammesse.** Postgres è suggerito ma non è vincolante: se preferisci, puoi usare **MySQL 8** o **MariaDB 11**. In tal caso vanno adattati pochi dettagli: l'immagine Docker (`mysql:8` o `mariadb:11` invece di `postgres:16-alpine`), le variabili d'ambiente per credenziali e nome DB (`MYSQL_ROOT_PASSWORD`, `MYSQL_USER`, `MYSQL_DATABASE` invece di `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB`), il path del volume dati (`/var/lib/mysql` invece di `/var/lib/postgresql/data`), il dialetto SQL nello script di init, e la libreria client Python (`pymysql` o `mysqlclient` invece di `psycopg2`). Resta intatta la topologia delle reti: il DB sta comunque solo in `db-net` e l'API resta l'unico ponte tra `frontend-net` e `db-net`. La scelta va motivata nel `README.md`.

## 4. Cosa deve dimostrare la demo

1. Aprire il browser su `http://localhost:8080` → la SPA carica e mostra l'elenco dei dati ottenuti via fetch dall'API.
2. Inserire un nuovo dato dal frontend → la pagina si aggiorna.
3. **Verifica di segmentazione 1**: dal container `frontend`, `getent hosts db` (o `nc -zv db 5432`) **fallisce** — non c'è risoluzione/raggiungibilità tra frontend e db.
4. **Verifica di segmentazione 2**: dal container `api`, `getent hosts db` e `nc -zv db 5432` **funzionano**.
5. **Verifica di segmentazione 3**: dal container `api`, `getent hosts frontend` funziona; dal container `db`, `getent hosts frontend` **fallisce**.
6. `docker network inspect frontend-net` e `db-net` mostrano i container attached e confermano la topologia.

## 5. Verifiche tecniche minime da documentare nel `README.md`

- `docker compose ps` e `docker network ls` (mostrare le due reti del progetto).
- `docker network inspect <progetto>_frontend-net` con i container collegati.
- I tre `nc -zv` / `getent hosts` di sopra, copiati dall'output reale.
- Screenshot della SPA che funziona nel browser.
- `curl http://localhost:8080/api/items` (se si proxia via nginx) o `curl http://localhost:<porta-api>/api/items` (se l'API è esposta).

## 6. Concetti chiave da padroneggiare

- **Reti Docker** come domini di broadcast/risoluzione: due container sono raggiungibili tra loro **solo se stanno sulla stessa rete**.
- **Multi-attach**: un container può stare su più reti (è il caso dell'`api`).
- **Service discovery via DNS interno**: il nome del servizio risolve a un IP solo dentro la rete in cui sta.
- **CORS**: perché il frontend (servito su `:8080`) e l'API (eventualmente su `:8000`) hanno bisogno di CORS, e cosa cambierebbe se l'API fosse proxata da nginx sotto lo stesso dominio.
- **Principio del minimo privilegio in rete**: il DB non deve vedere/sapere del frontend.

## 7. Spunti per la sezione "Riflessioni e punti aperti"

- Cosa cambierebbe se mettessi tutto su un'unica rete? Funzionerebbe lo stesso? Quali rischi introdurresti?
- Se al posto di Compose usassi Kubernetes, qual è il concetto equivalente alla "rete `db-net`"? (NetworkPolicy / Service ClusterIP, ecc.)
- Volendo aggiungere un servizio di analytics che legge dal DB **in sola lettura**, su quale rete lo metteresti?
- L'API è "stateless"? Lo chiederebbe il docente per scalarla a più repliche.

## 8. Possibili estensioni opzionali

- Configurare nginx come **reverse proxy** verso l'API (`location /api/ { proxy_pass http://api:8000/; }`), così il frontend e l'API sono sotto lo stesso origine e CORS sparisce. È un'estensione molto formativa.
- Aggiungere un container `db-replica` (in sola lettura) sulla `db-net`.
- Aggiungere un container `nginx-exporter` su una terza `monitoring-net` per metriche.
- Tutto via TLS (collega il progettino al pattern di A6).
