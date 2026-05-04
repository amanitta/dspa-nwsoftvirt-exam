# Progettino A5 — Frontend + API + DB (3-tier con Docker)

**Autore:** *(inserire nome e cognome)*
**Codice variante:** A5
**Repo:** *(inserire URL del repository pubblico)*

---

## 1. Obiettivo

Il progettino realizza un'applicazione web a tre livelli (3-tier) interamente containerizzata con Docker Compose. Un sito statico servito da nginx funge da frontend; le operazioni sui dati transitano attraverso una REST API Python/Flask; la persistenza è affidata a un database PostgreSQL. I tre container sono collegati tramite **due reti Docker separate**: `frontend-net` mette in comunicazione solo nginx e l'API, mentre `backend-net` mette in comunicazione solo l'API e il DB — il frontend non può mai raggiungere direttamente il database.

---

## 2. Architettura

```
Browser
  │  HTTP :8080
  ▼
┌──────────────────────────────────────────────────────────────────────┐
│  frontend-net  (bridge: a5_frontend_net)                             │
│                                                                      │
│  ┌──────────────────────────┐       ┌────────────────────────────┐  │
│  │  frontend  (nginx:1.27)  │──────►│  api  (Python 3.12/Flask)  │  │
│  │  porta host: 8080        │       │  porta interna: 5000       │  │
│  │  serve: nginx/index.html │       │  esposta solo su frontend- │  │
│  │  proxy /api/ → api:5000  │       │  net; connessa anche a     │  │
│  └──────────────────────────┘       │  backend-net               │  │
│                                     └────────────┬───────────────┘  │
└─────────────────────────────────────────────────-│──────────────────┘
                                                   │
┌──────────────────────────────────────────────────│──────────────────┐
│  backend-net  (bridge: a5_backend_net)            │                  │
│                                                   ▼                  │
│                              ┌─────────────────────────────────┐    │
│                              │  db  (postgres:16-alpine)        │    │
│                              │  porta 5432 NON esposta all'host │    │
│                              │  volume persistente: a5_db_data  │    │
│                              └─────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

**Componenti:**

| Container | Immagine base | Ruolo | Reti |
|-----------|---------------|-------|------|
| `a5_frontend` | `nginx:1.27-alpine` | Serve `index.html`; fa reverse-proxy di `/api/*` verso l'API | `frontend-net` |
| `a5_api` | build locale (Python 3.12) | REST API Flask; crea/legge note su PostgreSQL | `frontend-net` + `backend-net` |
| `a5_db` | `postgres:16-alpine` | Persistenza dati; porta 5432 raggiungibile solo via `backend-net` | `backend-net` |

**Flusso di una richiesta:**
1. Il browser chiama `GET /api/notes` su `localhost:8080`.
2. nginx (sull'interfaccia `frontend-net`) fa proxy verso `http://api:5000/notes`.
3. Flask interroga PostgreSQL via `db:5432` sulla rete `backend-net`.
4. La risposta JSON risale la catena fino al browser.

---

## 3. Prerequisiti

| Software | Versione testata | Note |
|---|---|---|
| Linux (Ubuntu 24.04 / Debian 12) | — | Testato su Ubuntu 24.04 LTS |
| Docker Engine | ≥ 26.x | `docker --version` |
| Docker Compose plugin | ≥ 2.27 | `docker compose version` |
| curl | qualsiasi | solo per i test da terminale |

> **Nota WSL2 (Windows):** il setup funziona identicamente su WSL2 Ubuntu 24.04; le porte sono raggiunte via `localhost` dal browser Windows.

---

## 4. Come riprodurre passo-passo

```bash
# 1. Clona il repository
git clone https://github.com/<utente>/<repo>.git
cd <repo>

# 2. Rendi eseguibili gli script
chmod +x scripts/setup.sh scripts/teardown.sh

# 3. Avvia lo stack (build + up + health-check)
#    Atteso: output "Stack is up! Open http://localhost:8080"
bash scripts/setup.sh

# 4. Verifica che tutti e tre i container siano "healthy" / "running"
#    Atteso: a5_frontend (Up), a5_api (healthy), a5_db (healthy)
docker compose ps

# 5. Apri il browser
#    Atteso: pagina "Notes Board" con campo di input
xdg-open http://localhost:8080   # oppure aprire manualmente il browser
```

> Se `setup.sh` si blocca in attesa dell'API, verificare i log con `docker compose logs api`.

---

## 5. Verifica del funzionamento

### 5.1 Interfaccia web

Aprire `http://localhost:8080`:  
- Digitare un testo nel campo "Write a note…" e premere **Add** (o Invio).  
- La nota deve apparire nell'elenco sottostante, con timestamp.  
- Il pulsante **✕** deve eliminare la nota dall'elenco e dal DB.

### 5.2 API da terminale

```bash
# Health-check dell'API (via nginx)
# Atteso: {"db": "reachable", "status": "ok"}
curl -s http://localhost:8080/api/health | python3 -m json.tool

# Creazione di una nota
# Atteso: JSON con id, content, created_at  (HTTP 201)
curl -s -X POST http://localhost:8080/api/notes \
     -H "Content-Type: application/json" \
     -d '{"content": "Verifica funzionamento A5"}' | python3 -m json.tool

# Lista note
# Atteso: array JSON con la nota appena creata
curl -s http://localhost:8080/api/notes | python3 -m json.tool
```

### 5.3 Isolamento di rete (punto chiave del progetto)

```bash
# Il container frontend NON deve poter raggiungere il DB sulla porta 5432.
# Atteso: "nc: getaddrinfo for host "db" port 5432: Name or service not known"
#         oppure connection refused/timeout → la rete backend-net non è visibile.
docker exec a5_frontend sh -c "nc -zv db 5432 2>&1 || true"

# Il container api deve invece raggiungere il DB senza problemi.
# Atteso: "open"
docker exec a5_api sh -c "nc -zv db 5432 2>&1"

# Ispezione delle reti: frontend-net ha solo frontend e api
# Atteso: "a5_frontend" e "a5_api" in Containers; "a5_db" assente
docker network inspect a5_frontend_net \
  --format '{{range $k,$v := .Containers}}{{$v.Name}} {{end}}'

# Ispezione backend-net: solo api e db
# Atteso: "a5_api" e "a5_db"; "a5_frontend" assente
docker network inspect a5_backend_net \
  --format '{{range $k,$v := .Containers}}{{$v.Name}} {{end}}'
```

### 5.4 Persistenza dei dati

```bash
# Riavvia solo il container API (simulazione crash/deploy)
docker compose restart api

# Le note devono essere ancora presenti (sono nel volume db)
curl -s http://localhost:8080/api/notes | python3 -m json.tool
```

### 5.5 Teardown

```bash
# Ferma e rimuove container, reti e volume
bash scripts/teardown.sh
# Atteso: nessun container/rete/volume con prefisso "a5_" rimasto
```

---

## 6. Riflessioni e punti aperti

**Cosa ho scoperto:**

- La separazione in due reti non richiede nessuna regola `iptables` esplicita: Docker gestisce automaticamente le regole di forwarding tra bridge. Tuttavia, il risultato è concreto: il container `frontend` non ha nemmeno una route verso `backend-net`, quindi qualunque tentativo di contattare il DB fallisce a livello DNS prima ancora che a livello TCP.

- Il container `api` funge da unico *gateway* tra i due tier. Questo è esattamente il pattern di sicurezza atteso: se un attaccante compromettesse il frontend (es. path traversal in nginx), non avrebbe accesso diretto al DB perché i due tier vivono su reti logicamente separate.

- Il `healthcheck` in Compose è essenziale: senza `depends_on: condition: service_healthy`, Flask tenterebbe di connettersi a PostgreSQL prima che il cluster sia pronto, e il container uscirebbe con errore. Il `init_db()` con retry è una seconda linea di difesa.

**Domande aperte / miglioramenti futuri:**

1. **Autenticazione API:** le route sono attualmente aperte. In produzione si aggiungerebbe un token Bearer o sessioni.
2. **HTTPS:** nginx potrebbe terminare TLS con un certificato self-signed (o Let's Encrypt in produzione).
3. **Portabilità cloud:** su AWS/GCP, `frontend-net` e `backend-net` diventerebbero *security group* o *VPC subnets* con regole analoghe. La logica di isolamento resta identica; cambia solo il piano di implementazione.
4. **Volume e backup:** il volume `a5_db_data` sopravvive al `docker compose down` ma viene rimosso da `docker compose down -v`. In un contesto reale si userebbe un backup periodico (pg_dump) o un managed DB.

---

## 7. Riferimenti

- [Docker Compose networking](https://docs.docker.com/compose/networking/)
- [Docker Bridge networks](https://docs.docker.com/network/drivers/bridge/)
- [Flask documentation](https://flask.palletsprojects.com/)
- [PostgreSQL Docker Hub](https://hub.docker.com/_/postgres)
- [nginx reverse proxy](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
- Slide hands-on del corso: `itp-2526-HandsOn.pptx` (prof. Salsano)
- `Docker_WSL2_Guida_Esercitazioni.md` — materiale del corso
