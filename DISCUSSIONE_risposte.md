# Preparazione alla discussione — Progettino A5

Questo documento raccoglie le domande tipiche che il docente può porre durante la discussione del progettino A5 (3-tier Docker: nginx + Flask API + PostgreSQL), con risposte ragionate e, dove utile, i comandi di verifica da mostrare in aula.

> **Uso consigliato:** leggi questo file *prima* della demo, non durante. L'obiettivo è interiorizzare il ragionamento, non leggere risposte a memoria.

---

## Domande generali (indipendenti dalla variante)

### D1 — Perché hai isolato così le reti? Cosa cambierebbe se collegassi tutto sulla stessa rete?

**Risposta:**

Ho creato due reti bridge separate: `frontend-net` (nginx ↔ api) e `db-net` (api ↔ db). L'`api` è l'unico container collegato a entrambe — è il solo punto di accesso al database.

Il motivo è il **principio del minimo privilegio**: ogni tier può parlare solo con chi gli è strettamente necessario. In pratica:

- nginx non ha nessuna interfaccia su `db-net`, quindi non può nemmeno risolvere il nome DNS `db`. Se un attaccante sfruttasse una vulnerabilità di nginx (es. path traversal, SSRF), non troverebbe il DB sulla rete.
- La porta 5432 di PostgreSQL non è pubblicata sull'host (`expose` ≠ `ports`): è raggiungibile solo dai container su `db-net`.

**Se mettessi tutto sulla stessa rete:** funzionerebbe ugualmente dal punto di vista applicativo, ma nginx avrebbe accesso diretto alla porta 5432. Un attaccante che compromette il frontend avrebbe accesso diretto al database — esattamente il rischio che la separazione di rete vuole evitare. Perderei anche la chiarezza architetturale: non sarebbe più evidente quali tier si parlano e quali no.

**Verifica live (le tre verifiche richieste dalla specifica):**

> Nota: `nc` non è incluso nelle immagini slim/alpine. Si usa `nslookup` (presente in tutte le immagini alpine) e `python3 -c socket` (disponibile nell'immagine Python dell'API).

```bash
# Verifica 1 — frontend NON vede il DB (DNS: NXDOMAIN)
# Atteso: "server can't find db... NXDOMAIN"
docker exec a5_frontend nslookup db

# Verifica 2 — api vede il DB (DNS risolve l'IP del container db)
# Atteso: ('172.22.0.x', 5432)
docker exec a5_api python3 -c \
  "import socket; print(socket.getaddrinfo('db',5432)[0][4])"

# Verifica 3 — api vede frontend; db NON vede frontend
# Atteso api: ('172.21.0.x', 80)
docker exec a5_api python3 -c \
  "import socket; print(socket.getaddrinfo('frontend',80)[0][4])"
# Atteso db: "server can't find frontend... NXDOMAIN"
docker exec a5_db nslookup frontend
```

---

### D2 — Cosa succede se distruggo questo container? I dati sopravvivono? E le configurazioni?

**Risposta — per ogni container:**

| Container distrutto | Dati applicativi | Configurazione |
|---|---|---|
| `a5_frontend` (nginx) | nessun dato persistente | `index.html` e `nginx.conf` sono bind-mount dal repo → sopravvivono; il container si ricrea con `docker compose up` |
| `a5_api` (Flask) | nessun stato locale; le spese stanno nel DB | il codice è nel repo; il container si ricrea senza perdita |
| `a5_db` (PostgreSQL) | **dipende**: `docker compose down` (senza `-v`) lascia il volume `a5_db_data` intatto; `docker compose down -v` lo elimina | la configurazione (utente/password/db) è nelle variabili d'ambiente in `compose.yaml` |

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

# 4. Con down -v (teardown completo) il volume viene rimosso → dati persi
#    bash scripts/teardown.sh
```

---

### D3 — In che modalità di rete sei? Chi vede chi e perché?

**Risposta:**

Uso esclusivamente reti **bridge** di Docker (driver `bridge`), la modalità predefinita per container su host Linux. Ogni rete bridge è implementata a livello kernel come dispositivo virtuale (`br-<id>`) con regole `iptables`/`nftables` gestite automaticamente da Docker.

**Chi vede chi:**

```
Host  ──:8080──►  a5_frontend  ──frontend-net──►  a5_api  ──db-net──►  a5_db
                                                     │
                             (nessuna route verso db-net)
                  a5_frontend  ✗─────────────────────────────────────►  a5_db
                  a5_db        ✗────────────────────────────────────►   a5_frontend
```

- L'**host** raggiunge solo `a5_frontend` sulla porta 8080 (unica `ports:` pubblicata).
- **a5_frontend** risolve `api` via DNS interno su `frontend-net`, ma non ha interfaccia su `db-net`.
- **a5_api** è l'unico container su entrambe le reti: può parlare con `frontend` e con `db`.
- **a5_db** è solo su `db-net`: non può raggiungere `frontend` e non è raggiungibile dall'host.

**Perché Docker garantisce questo:** ogni rete bridge ha il proprio spazio IP e il proprio namespace DNS. Il forwarding tra bridge diversi è bloccato di default; un container vede solo i nomi/IP dei container sulla stessa rete.

---

### D4 — Se questo setup andasse in cloud pubblico, quale parte cambierebbe e quale resterebbe identica?

**Risposta:**

| Componente | On-premise / locale | Cloud pubblico (es. AWS) |
|---|---|---|
| Logica applicativa (Flask, nginx, SQL) | identica | **identica** — i container si spostano senza modifiche |
| `frontend-net` / `db-net` | reti Docker bridge | **Security Groups** + **VPC Subnets** (subnet pubblica per il load balancer, subnet privata per API e DB) |
| Porta 8080 esposta | `ports: "8080:80"` | **Application Load Balancer** su porta 443 con certificato ACM |
| Porta 5432 non esposta | `expose:` senza `ports:` | DB in subnet privata, oppure **RDS** managed — la stringa di connessione cambia, il codice no |
| Volume `a5_db_data` | named volume locale | **EBS** (volume persistente) o RDS con backup automatici |
| Immagini Docker | build locale | registrate su **ECR**, deploy su **ECS** o **EKS** |
| `docker compose up` | comando manuale | pipeline CI/CD (GitHub Actions → ECR → ECS task definition) |

**Cosa resta identico:** struttura a tre tier, separazione su reti diverse, API come unico mediatore, le REST API di Flask, la struttura SQL. Il cloud cambia il *piano di implementazione*, non l'architettura logica.

---

## Domande specifiche al progettino A5

### D5 — Cosa significa che l'`api` è su due reti? Cos'è il "multi-attach"?

**Risposta:**

In Docker Compose si può assegnare un container a più reti elencandole nella chiave `networks:` del servizio. Il container ottiene un'interfaccia di rete virtuale (e quindi un IP distinto) per ogni rete a cui appartiene.

Nel nostro caso `a5_api` ha:
- un'interfaccia su `a5_frontend_net` (IP es. `172.20.0.3`) — con cui nginx lo raggiunge
- un'interfaccia su `a5_db_net` (IP es. `172.21.0.2`) — con cui raggiunge il DB

Questo è il **multi-attach** ed è esattamente il pattern che trasforma l'API nel *gateway controllato* tra i due tier. Senza multi-attach non ci sarebbe modo di far transitare il traffico da `frontend-net` a `db-net` senza esporre porte sull'host.

**Verifica:**
```bash
# Si vedono i due IP su reti diverse
docker exec a5_api python3 -c "
import socket
for net, ip in [('db-net', 'db'), ('frontend-net', 'frontend')]:
    addr = socket.getaddrinfo(ip, None)[0][4][0]
    print(f'{net}: {ip} -> {addr}')
"
# oppure con docker inspect:
docker inspect a5_api --format \
  '{{range $net,$cfg := .NetworkSettings.Networks}}{{$net}}: {{$cfg.IPAddress}}{{"\n"}}{{end}}'
```

---

### D6 — Perché il frontend non ha bisogno di CORS, dato che parla con un'API su una porta diversa?

**Risposta:**

Normalmente CORS è necessario quando il browser fa una richiesta verso un'**origine diversa** (schema + host + porta). Se il frontend fosse su `http://localhost:8080` e l'API su `http://localhost:5000`, il browser blocherebbe la richiesta perché le porte differiscono → origini diverse → CORS obbligatorio.

Nel nostro setup nginx fa da **reverse proxy**: `location /api/ { proxy_pass http://api:5000/; }`. Il browser non sa nulla della porta 5000; vede solo richieste verso `http://localhost:8080/api/...` — stessa porta, stessa origine. CORS non è necessario e non è configurato.

**Cosa cambierebbe senza il reverse proxy:** se il frontend facesse `fetch("http://localhost:5000/expenses")` direttamente, Flask dovrebbe rispondere con `Access-Control-Allow-Origin: http://localhost:8080` e bisognerebbe aggiungere `flask-cors` alle dipendenze. Con il proxy, questo problema scompare — ed è uno dei motivi per cui il pattern reverse-proxy è quasi universale in produzione.

---

### D7 — L'API è "stateless"? Si potrebbe scalare a più repliche?

**Risposta:**

Sì, l'API è **stateless**: ogni richiesta HTTP contiene tutte le informazioni necessarie per essere processata. Flask non mantiene sessioni in memoria tra una chiamata e l'altra; tutto lo stato (le spese) vive nel database PostgreSQL.

**Conseguenza:** si possono avviare N repliche dell'`api` senza nessuna modifica al codice:

```yaml
# In compose.yaml, basta aggiungere:
api:
  deploy:
    replicas: 3
```

Docker Compose (o un orchestratore come Kubernetes) distriburisce il traffico tra le repliche. Ognuna si connette allo stesso DB — il volume `a5_db_data` è il solo stato condiviso.

**Limite attuale:** il DB è a singola istanza, quindi è il collo di bottiglia. In produzione si userebbe un DB con replica (PostgreSQL streaming replication, o RDS Multi-AZ).

---

### D8 — Perché hai messo il `GROUP BY` in PostgreSQL invece di recuperare tutto in Python e calcolare lì?

**Risposta:**

Tre motivi:

1. **Efficienza di rete interna (`db-net`):** con 10 000 spese, `SELECT * FROM expenses` farebbe viaggiare 10 000 righe su `db-net`; con `GROUP BY` viaggiano al massimo 8 righe (una per categoria).

2. **Ottimizzazione del DB:** PostgreSQL usa hash aggregation con indici e statistiche interne — molto più efficiente di un loop Python su liste.

3. **Correttezza numerica:** la colonna è `NUMERIC(10,2)`, non float; l'aggregazione in PostgreSQL preserva la precisione decimale senza errori di arrotondamento.

```bash
curl -s http://localhost:8080/api/expenses/summary | python3 -m json.tool
```

---

### D9 — Se aggiungessi un servizio di analytics che legge il DB in sola lettura, su quale rete lo metteresti?

**Risposta:**

Su `db-net` soltanto, **senza** `frontend-net`. L'analytics ha bisogno di leggere dati dal DB ma non deve ricevere traffico dal frontend né esporre endpoint all'esterno.

```yaml
analytics:
  image: my-analytics-service
  networks:
    - db-net       # può raggiungere il DB
                   # NON su frontend-net → non raggiungibile da nginx o dal browser
  environment:
    DB_HOST: db
    DB_ACCESS: readonly
```

Per renderlo davvero read-only, si creerebbe un utente PostgreSQL con solo `SELECT`:
```sql
CREATE USER analytics_user WITH PASSWORD 'secret';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_user;
```

Questo è un secondo esempio di **minimo privilegio**: il servizio analytics vede solo ciò che gli serve (il DB) e non è raggiungibile da chi non ne ha bisogno (il frontend).

---

### D10 — Se usassi Kubernetes invece di Docker Compose, qual è il concetto equivalente alle reti `frontend-net` e `db-net`?

**Risposta:**

In Kubernetes la separazione di rete si ottiene principalmente con le **NetworkPolicy** (oggetti Kubernetes che definiscono regole di ingress/egress a livello di pod) e con la scelta del tipo di **Service**:

| Docker Compose | Kubernetes equivalente |
|---|---|
| `frontend-net` / `db-net` (reti bridge separate) | **NetworkPolicy** che limita quali pod possono parlare con quali (es. solo i pod `api` possono inviare traffico ai pod `db`) |
| `expose:` senza `ports:` (nessuna porta sull'host) | **Service di tipo `ClusterIP`** — raggiungibile solo dall'interno del cluster, non dall'esterno |
| `ports: "8080:80"` (esposto sull'host) | **Service di tipo `NodePort`** o, in cloud, **LoadBalancer** |
| DNS interno Docker (`db` risolve all'IP del container) | **Service DNS interno** di Kubernetes (`db.default.svc.cluster.local`) |
| Multi-attach (api su due reti) | Pod `api` soggetto a NetworkPolicy che gli permettono sia di ricevere da `frontend` sia di inviare a `db` |

**Differenza importante:** in Docker Compose la separazione è a livello di *rete* (un container non ha route verso un'altra rete). In Kubernetes di default tutti i pod si vedono — la separazione è *esplicita* e va definita con NetworkPolicy. Questo rende Kubernetes più flessibile ma richiede più configurazione per raggiungere lo stesso livello di isolamento.

---

### D11 — Il Dockerfile usa un build multi-stage. Perché? Cosa cambierebbe con un single-stage?

**Risposta:**

Il Dockerfile ha due stage:
- `builder`: installa `pip` e tutti i pacchetti in `/install` su `python:3.12-slim`.
- Stage finale (runtime): copia solo `/install` e il codice sorgente — **non** contiene `pip`, i sorgenti di compilazione di `psycopg2`, né la cache di pip.

**Vantaggio:** immagine finale più piccola (meno superficie di attacco) e più sicura (nessun toolchain di build disponibile a un attaccante che entrasse nel container). Con un single-stage avrei la stessa funzionalità ma un'immagine più grande e con più strumenti esposti.

---

### D12 — Il `healthcheck` usa `python -c "import urllib.request; ..."`. Perché non `curl` o `wget`?

**Risposta:**

`python:3.12-slim` non include `curl` né `wget`. Usare `urllib.request` (stdlib Python) non richiede nessuna installazione aggiuntiva né layer extra nel Dockerfile. È la soluzione a zero dipendenze.

---

### D13 — `depends_on: condition: service_healthy` vs `depends_on` semplice — qual è la differenza?

**Risposta:**

`depends_on: db` garantisce solo che Docker *avvii* il container `db` prima di `api`, non che PostgreSQL sia pronto. `condition: service_healthy` aspetta che il `healthcheck` (`pg_isready`) restituisca successo. Il progetto ha anche un doppio livello: `init_db()` in `app.py` riprova la connessione fino a 10 volte con pausa di 2 secondi, coprendo i casi limite in cui il container risulta healthy ma PostgreSQL non è ancora del tutto pronto.

---

## Checklist pre-demo (5 minuti prima)

- [ ] `docker compose ps` → tutti e tre i container **Up / healthy**
- [ ] `docker network ls --filter name=a5_` → due reti visibili (`a5_frontend_net`, `a5_db_net`)
- [ ] Browser aperto su `http://localhost:8080` → pagina caricata
- [ ] Almeno 3 spese già inserite (almeno 2 categorie diverse, per mostrare il riepilogo)
- [ ] Terminale 1: comandi `curl` della sezione 5.2 del README pronti
- [ ] Terminale 2: comandi `getent hosts` della sezione 5.3 del README pronti
- [ ] `scripts/teardown.sh` pronto da mostrare alla fine
- [ ] Connessione internet **non necessaria** — tutto gira offline
