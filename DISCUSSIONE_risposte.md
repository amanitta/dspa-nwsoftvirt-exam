# Preparazione alla discussione — Progettino A5

Questo documento raccoglie le domande tipiche che il docente può porre durante la discussione del progettino A5 (3-tier Docker: nginx + Flask API + PostgreSQL), con risposte ragionate e, dove utile, i comandi di verifica da mostrare in aula.

> **Uso consigliato:** leggi questo file *prima* della demo, non durante. L'obiettivo è interiorizzare il ragionamento, non leggere risposte a memoria.

---

## Domande generali (indipendenti dalla variante)

### D1 — Perché hai isolato così le reti? Cosa cambierebbe se collegassi tutto sulla stessa rete?

**Risposta:**

Ho creato due reti bridge separate: `frontend-net` (nginx ↔ api) e `backend-net` (api ↔ db). L'api è l'unico container collegato a entrambe — è il solo punto di accesso al database.

Il motivo è il **principio del minimo privilegio**: ogni tier può parlare solo con chi gli è strettamente necessario. In pratica:

- nginx non ha nessuna interfaccia su `backend-net`, quindi non può nemmeno risolvere il nome DNS `db`. Se un attaccante sfruttasse una vulnerabilità di nginx (es. path traversal, SSRF), non troverebbe il DB sulla rete.
- La porta 5432 di PostgreSQL non è pubblicata sull'host (`expose` ≠ `ports`): è raggiungibile solo dai container su `backend-net`.

**Se mettessi tutto sulla stessa rete:** funzionerebbe ugualmente dal punto di vista applicativo, ma nginx avrebbe accesso diretto alla porta 5432. Un eventuale attaccante che compromette il frontend avrebbe accesso diretto al database — esattamente il rischio che la separazione di rete vuole evitare. Inoltre, perderei la chiarezza architetturale: non sarebbe più evidente quali tier si parlano e quali no.

**Verifica live:**
```bash
# frontend non vede il DB (errore DNS o timeout)
docker exec a5_frontend sh -c "nc -zv db 5432 2>&1 || true"

# api vede il DB
docker exec a5_api sh -c "nc -zv db 5432 2>&1"

# ispezione delle reti
docker network inspect a5_frontend_net --format '{{range $k,$v := .Containers}}{{$v.Name}} {{end}}'
docker network inspect a5_backend_net  --format '{{range $k,$v := .Containers}}{{$v.Name}} {{end}}'
```

---

### D2 — Cosa succede se distruggo questo container? I dati sopravvivono? E le configurazioni?

**Risposta — per ogni container:**

| Container distrutto | Dati applicativi | Configurazione |
|---|---|---|
| `a5_frontend` (nginx) | nessun dato persistente | `index.html` e `nginx.conf` sono bind-mount dal repo → sopravvivono; il container si ricrea con `docker compose up` |
| `a5_api` (Flask) | nessun stato locale; le spese stanno nel DB | il codice è nel repo; il container si ricrea senza perdita |
| `a5_db` (PostgreSQL) | **dipende**: se uso `docker compose down` (senza `-v`) il volume `a5_db_data` rimane e i dati sopravvivono; se uso `docker compose down -v` il volume viene eliminato e i dati sono persi | la configurazione (utente/password/db) è nelle variabili d'ambiente in `compose.yaml` |

**Dimostrazione pratica:**
```bash
# 1. Aggiungo una spesa
curl -s -X POST http://localhost:8080/api/expenses \
     -H "Content-Type: application/json" \
     -d '{"amount": 9.99, "category": "Altro", "description": "Test persistenza"}'

# 2. Distruggo e ricreo SOLO il container API (non il volume)
docker compose rm -sf api
docker compose up -d api

# 3. Le spese sono ancora lì (erano nel DB, non nell'API)
curl -s http://localhost:8080/api/expenses | python3 -m json.tool

# 4. Se invece faccio down -v (teardown completo):
#    bash scripts/teardown.sh
#    → il volume a5_db_data viene rimosso → dati persi
```

---

### D3 — In che modalità di rete sei? Chi vede chi e perché?

**Risposta:**

Uso esclusivamente reti **bridge** di Docker (driver `bridge`), che è la modalità predefinita per i container su host Linux. Ogni rete bridge è implementata a livello kernel come un dispositivo virtuale (`br-<id>`) con regole `iptables`/`nftables` gestite automaticamente da Docker.

**Chi vede chi:**

```
Host  ──:8080──►  a5_frontend  ──frontend-net──►  a5_api  ──backend-net──►  a5_db
                                                     │
                                  (nessuna route)    │   (nessuna route)
                  a5_frontend  ✗──────────────────────────────────────►  a5_db
```

- L'**host** raggiunge solo `a5_frontend` sulla porta 8080 (unica `ports:` pubblicata).
- **a5_frontend** (nginx) raggiunge `a5_api:5000` tramite la DNS interna di Docker su `frontend-net`, ma non ha interfaccia su `backend-net`.
- **a5_api** (Flask) raggiunge sia `a5_frontend` (non le serve, ma è sulla stessa rete) sia `a5_db:5432` tramite `backend-net`.
- **a5_db** (PostgreSQL) è raggiungibile solo da `a5_api`; nessun altro container o l'host possono aprire connessioni TCP verso di esso.

**Perché Docker garantisce questo:** ogni rete bridge ha il proprio spazio di indirizzamento IP (`172.x.x.x`) e le regole di forwarding tra bridge diversi sono bloccate di default da Docker (`com.docker.network.bridge.enable_icc=true` vale solo *dentro* la stessa rete; tra reti diverse il traffico non è instradato a meno di pubblicare porte).

---

### D4 — Se questo setup andasse in cloud pubblico, quale parte cambierebbe e quale resterebbe identica?

**Risposta:**

| Componente | On-premise / locale | Cloud pubblico (es. AWS) |
|---|---|---|
| Logica applicativa (Flask, nginx, SQL) | identica | **identica** — i container si spostano senza modifiche |
| Reti Docker bridge | `frontend-net` / `backend-net` | rimpiazzate da **Security Groups** + **VPC Subnets** (es. subnet pubblica per il load balancer, subnet privata per API e DB) |
| Porta 8080 esposta | `ports: "8080:80"` sul daemon Docker locale | **Application Load Balancer** (porta 443 con certificato ACM) davanti al container nginx |
| Porta 5432 non esposta | `expose:` senza `ports:` | DB in subnet privata senza route pubblica; oppure sostituita da **RDS** (managed PostgreSQL) — la stringa di connessione cambia, il codice no |
| Volume `a5_db_data` | named volume sul filesystem locale | **EBS** (volume persistente) o **RDS** con backup automatici |
| Immagini Docker | build locale | registrate su **ECR** (Elastic Container Registry), deploy su **ECS** o **EKS** |
| `docker compose up` | comando manuale | rimpiazzato da pipeline CI/CD (GitHub Actions → ECR → ECS task definition) |

**Cosa resta identico:** la struttura a tre tier, la separazione dei tier su reti diverse, il fatto che l'API è l'unico mediatore tra frontend e DB, le API REST di Flask, la struttura SQL. Il cloud cambia *il piano di implementazione*, non l'architettura logica.

---

## Domande specifiche al progettino A5

### D5 — Perché hai messo il `GROUP BY` in PostgreSQL invece di recuperare tutto in Python e calcolare lì?

**Risposta:**

Ci sono tre motivi:

1. **Efficienza di rete interna:** se ci fossero 10 000 spese e facessi `SELECT * FROM expenses`, Flask riceverebbe 10 000 righe su `backend-net` per poi buttarle via dopo la somma. Con `GROUP BY` PostgreSQL restituisce al massimo N righe (una per categoria, N ≤ 8 nel nostro caso), indipendentemente dal numero di spese.

2. **Sfruttare ciò per cui il DB è progettato:** i database relazionali hanno indici, statistiche interne e algoritmi di aggregazione ottimizzati (hash aggregation, sort-merge). Python con un loop su liste è molto meno efficiente per questo tipo di operazione.

3. **Leggibilità e correttezza:** la query SQL dichiara *cosa* voglio (`SUM`, `AVG`, `MIN`, `MAX` per categoria); non devo gestire manualmente il raggruppamento, i casi limite (categoria con una sola spesa) né la precisione numerica (PostgreSQL usa `NUMERIC`, non float).

**Verifica:**
```bash
curl -s http://localhost:8080/api/expenses/summary | python3 -m json.tool
# Si vede che per ogni categoria arrivano già i valori aggregati,
# non l'elenco grezzo delle spese.
```

---

### D6 — Il container `api` usa un Dockerfile multi-stage. Perché? Cosa cambierebbe con un single-stage?

**Risposta:**

Il Dockerfile ha due stage:
- `builder`: parte da `python:3.12-slim`, installa `pip` e tutti i pacchetti in `/install`.
- Stage finale (runtime): parte di nuovo da `python:3.12-slim`, copia solo `/install` e il codice sorgente.

**Vantaggio:** l'immagine finale non contiene `pip`, i metadati dei pacchetti, i sorgenti di compilazione di `psycopg2`, né la cache di pip. Risultato: immagine più piccola (meno superficie di attacco, meno banda per il pull in produzione) e più sicura (niente strumenti di build disponibili a un eventuale attaccante).

Con un **single-stage** avrei la stessa immagine di base ma con tutto il toolchain di build incluso — funzionerebbe ugualmente, ma l'immagine sarebbe più grande e meno sicura.

---

### D7 — Il `healthcheck` del container `api` usa `python -c "import urllib.request; ..."` invece di `curl` o `wget`. Perché?

**Risposta:**

L'immagine `python:3.12-slim` è volutamente minimale: non include `curl` né `wget` (sono strumenti di sistema, non Python). Installare uno dei due solo per il healthcheck avrebbe aumentato la dimensione dell'immagine e aggiunto una dipendenza non necessaria al runtime. Il modulo `urllib.request` fa parte della stdlib Python, è sempre disponibile nell'immagine e non richiede nulla di esterno.

Alternativa valida: aggiungere `RUN apt-get install -y curl` nel Dockerfile e usare `CMD ["curl", "-f", "http://localhost:5000/health"]` — funzionerebbe, ma al costo di un layer aggiuntivo nell'immagine.

---

### D8 — Cosa succede se elimino il volume `a5_db_data` senza fermare i container?

**Risposta:**

Docker non permette di rimuovere un volume mentre è montato da un container in esecuzione: il comando `docker volume rm a5_db_data` restituisce un errore (`volume is in use`). Questo è un meccanismo di protezione del daemon Docker.

Per eliminare il volume bisogna prima fermare (o rimuovere) il container `a5_db`. Lo script `teardown.sh` usa `docker compose down -v` che fa le due operazioni in ordine: prima ferma e rimuove i container, poi rimuove il volume.

---

### D9 — La porta 5432 di PostgreSQL non è esposta sull'host. Come faccio a ispezionare il DB se ho bisogno di debug?

**Risposta:**

Ci sono due approcci, entrambi senza toccare `compose.yaml`:

```bash
# Approccio 1: docker exec — si entra nel container e si usa psql
docker exec -it a5_db psql -U notesuser -d notesdb

# Approccio 2: docker compose exec (equivalente)
docker compose exec db psql -U notesuser -d notesdb

# Dentro psql:
\dt                          -- lista le tabelle
SELECT * FROM expenses;      -- vede tutte le spese
SELECT category, SUM(amount) FROM expenses GROUP BY category;
\q
```

In alternativa, per strumenti grafici (DBeaver, TablePlus), si può aggiungere temporaneamente `ports: "5432:5432"` in `compose.yaml` solo durante il debug, e rimuoverla prima di committare.

---

### D10 — `depends_on: condition: service_healthy` è sufficiente a garantire che l'API parta dopo il DB? Non basta `depends_on: db`?

**Risposta:**

`depends_on: db` (senza condition) garantisce solo che Docker *avvii* il container `db` prima di `api` — non che PostgreSQL sia pronto ad accettare connessioni. Il processo `postgres` impiega alcuni secondi per inizializzare il cluster, creare i file di dati e mettersi in ascolto.

`condition: service_healthy` aspetta invece che il `healthcheck` definito per `db` (`pg_isready -U notesuser -d notesdb`) restituisca esito positivo. Solo a quel punto Docker avvia `api`.

Il doppio livello di protezione nel progetto:
1. `depends_on: condition: service_healthy` — Compose non avvia `api` finché `db` non è healthy.
2. `init_db()` con retry in `app.py` — anche se per qualche motivo Flask parte prima che il DB sia completamente pronto, riprova fino a 10 volte prima di arrendersi.

---

## Checklist pre-demo (5 minuti prima)

- [ ] `docker compose ps` → tutti e tre i container **Up / healthy**
- [ ] Browser aperto su `http://localhost:8080` → pagina caricata
- [ ] Almeno 2-3 spese già inserite (per mostrare il riepilogo con più categorie)
- [ ] Terminale pronto con i comandi `curl` della sezione 5.2 del README
- [ ] `scripts/teardown.sh` aperto in un secondo terminale (da mostrare alla fine)
- [ ] Connessione internet **non necessaria** — tutto gira offline
