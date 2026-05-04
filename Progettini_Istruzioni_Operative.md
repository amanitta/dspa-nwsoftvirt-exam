# Progettini — istruzioni operative

Corso di *Network Virtualization and Softwarization* — Master in Data Science per la Pubblica Amministrazione (a.a. 2025/2026, prof. Stefano Salsano).

Questo documento descrive **cosa devi consegnare** se scegli la modalità "progettino + discussione" come alternativa alla prova scritta. Il catalogo dei 20 progettini disponibili e la pagina di prenotazione sono in un documento separato (`Progettini_Lista_Prenotazioni.md`).

## 1. Riepilogo in poche righe

- Scegli **un progettino** dal catalogo e prenotalo scrivendo il tuo nome nella tabella di prenotazione.
- Realizzalo in autonomia (effort previsto: tra mezza e una giornata di lavoro effettivo).
- Pubblica il risultato come **repository GitHub pubblico**.
- Il giorno dell'esame, fai una **demo live di circa 5 minuti** + breve discussione.
- Il **report `README.md`** scritto in parallelo al progetto è parte integrante della consegna.

## 2. Effort atteso e tempistiche

L'effort tecnico previsto è di **mezza giornata - una giornata** di lavoro effettivo. Il report `README.md` va scritto **in parallelo** al lavoro tecnico, non a fine progetto: prendere appunti man mano è il modo più efficace per non dimenticare i dettagli.

L'obiettivo non è quello di raggiungere un progetto funzionante e perfetto al 100% (se ci riuscite, meglio!) ma descrivere quello che siete riusciti a fare nel tempo di cui sopra.

## 3. Struttura del repo GitHub

Il repository deve essere **pubblico** (così il docente può visitarlo senza account specifici). Naming consigliato per il repo:

```
nv-progettino-<codice-variante>-<cognome>
```

ad esempio: `nv-progettino-A1-rossi`, `nv-progettino-D5-bianchi`.

Struttura minima delle cartelle:

```
.
├── README.md             # report del progetto (vedi sezione 4)
├── compose.yaml          # se la variante usa Docker Compose
├── Dockerfile            # se la variante richiede una build di immagine
├── scripts/
│   ├── setup.sh          # script per avviare l'esperimento
│   └── teardown.sh       # script per pulire al termine
├── src/                  # eventuale codice applicativo (Python, ecc.)
├── screenshots/          # 3-5 screenshot della demo funzionante
└── (eventuali altre cartelle: vagrant/, vbox-config/, namespace/, ecc.)
```

Non tutte le cartelle sono obbligatorie: dipendono dal tipo di progettino. Per un progettino di famiglia B (network namespace), ad esempio, al posto di `compose.yaml` ci sarà uno script bash che crea i namespace e configura veth/route. Per un progettino di famiglia C (VirtualBox), invece di codice ci saranno screenshot di configurazione e magari un file `Vagrantfile` o un export `.ova` se applicabile.

Sul commit "stato finale" della consegna, applica un **tag** `v1.0`:

```bash
git tag -a v1.0 -m "Versione consegnata per discussione"
git push origin v1.0
```

In modo che, anche se dopo la discussione modifichi qualcosa, lo stato discusso resti tracciato.

## 4. Struttura del report `README.md`

Il `README.md` è il documento di riferimento che il docente legge **prima** della discussione. Deve permettergli di capire in 5-10 minuti cosa hai fatto, perché, e come riprodurlo. Struttura suggerita:

```markdown
# <Titolo del progettino>

**Autore:** Mario Rossi
**Codice variante:** A1
**Repo:** https://github.com/.../nv-progettino-A1-rossi

## 1. Obiettivo

(2-4 righe: cosa fa il progettino e perché. Un paragrafo, niente liste.)

## 2. Architettura

(Descrizione delle componenti — container, VM, namespace, reti — e di
come comunicano tra loro. Una piccola figura ASCII art o un'immagine in
screenshots/ aiutano molto.)

## 3. Prerequisiti

(Cosa deve avere installato chi vuole riprodurre il tuo lavoro:
WSL2 Ubuntu 24.04, Docker Engine, VirtualBox 7.x, ecc. Indicare le versioni.)

## 4. Come riprodurre passo-passo

(Sequenza di comandi numerati che, eseguiti su un sistema con i prerequisiti,
porta dal repo appena clonato allo stato in cui la demo "funziona".
Ogni comando deve essere COMMENTATO con cosa ci si aspetta in output.)

## 5. Verifica del funzionamento

(I comandi/azioni di verifica che dimostrano che il progettino funziona:
ping da X a Y, curl su porta Z, screenshot dell'output atteso, ecc.)

## 6. Riflessioni e punti aperti

(Cosa hai scoperto facendolo, eventuali difficoltà incontrate, cosa
miglioreresti, eventuali domande aperte. Non è un riempitivo: è la
parte che meglio mostra che hai capito ciò che hai fatto.)

## 7. Riferimenti

(Link a documentazione ufficiale, articoli, slide del corso, guide
dei materiali del corso che hai usato.)
```

Lunghezza ragionevole: **2-5 pagine** una volta renderizzato. Se è molto più corto rischi di non avere abbastanza dettaglio per riprodurre il lavoro; se è molto più lungo, probabilmente stai scrivendo prosa che la demo mostra meglio.

## 5. Demo live (circa 5 minuti)

In aula avrai circa **5 minuti** per la demo, più qualche minuto di discussione. Suggerimento per organizzarla:

1. **30 secondi**: di cosa si tratta (una frase per dire l'obiettivo, una per dire cosa si vedrà tra poco).
2. **3 minuti**: esecuzione live. Aprire il terminale (o VirtualBox), eseguire i comandi chiave (idealmente preparati in `scripts/setup.sh` o equivalente), mostrare l'output. Se qualche passaggio richiede tempo (es. `docker compose up` con build), avviare prima e mentre carica spiegare.
3. **1 minuto**: la verifica. Comando o test che dimostra che il sistema fa quello che deve fare (curl, ping, ispezione di una porta non esposta che non risponde, ecc.).
4. **30 secondi**: una "domanda di riflessione" che hai già documentato nel `README` — per dare il via alla discussione.

Suggerimenti pratici:

- Se la demo richiede più finestre di terminale (es. una per il main namespace e una per `ns2`), aprile **prima** di iniziare e organizzale in modo visibile.
- **Non** affidarti a una connessione Internet stabile in aula: tutto ciò che richiede pull di immagini Docker o `apt install` deve essere stato fatto già a casa, in modo che la demo sia offline.
- Se il tuo progettino crea risorse "rumorose" (regole iptables, routing, NAT), prepara anche il `teardown.sh` e mostralo: pulire dopo la demo è parte del professionalismo del lavoro.

## 6. Discussione

Dopo la demo, il docente farà 2-3 domande. Le domande tipiche, indipendentemente dalla variante:

- Perché hai isolato così le reti? Cosa cambierebbe se collegassi tutto sulla stessa rete?
- Cosa succede se distruggo questo container/VM/namespace? I dati sopravvivono? E le configurazioni?
- In che modalità di rete sei? Chi vede chi e perché?
- Se questo setup andasse in cloud pubblico, quale parte cambierebbe e quale resterebbe identica?

Le **domande di riflessione** già scritte nel tuo `README.md` (sezione 6) sono il modo migliore per anticipare e indirizzare la discussione.

## 7. Criteri di valutazione

Il giudizio si basa su quattro elementi, di peso comparabile:

- **Funzionamento della demo**: il progettino fa quello che deve fare, è riproducibile da zero seguendo le istruzioni del `README`.
- **Qualità del report `README.md`**: è chiaro, leggibile, copre obiettivo / architettura / passi / verifica / riflessioni; un terzo lettore potrebbe riprodurre tutto.
- **Comprensione mostrata in discussione**: le domande del docente trovano risposte non superficiali; lo studente sa raccontare *perché* ha fatto certe scelte, non solo *cosa* ha fatto.
- **Cura tecnica**: scelta delle porte, dei nomi, dei volumi, dei range IP è coerente; non ci sono regole "sporche" rimaste a giro; lo script di teardown ripulisce davvero.

Non è richiesto che il progettino sia "originale" o che vada oltre il perimetro descritto nel catalogo: è perfettamente accettabile (anzi, consigliato) restare entro la traccia e farla bene.

## 8. Suggerimenti generali

- **Inizia subito a scrivere il `README.md`** quando inizi il progettino, non quando hai finito. La memoria fresca dei comandi che funzionano è preziosa.
- **Versiona via git fin da subito**: commit piccoli e frequenti aiutano a recuperare quando qualcosa si rompe.
- Se rimani bloccato su un dettaglio per più di mezz'ora, **chiedi al docente** invece di proseguire ad oltranza. È pensato come un progetto da una giornata, non da una settimana.
- Lo **screenshot** è il tuo migliore amico per dimostrare che la demo funzionava al momento della consegna, anche se per qualche motivo in aula la rete inceppa.

## 9. Riferimenti rapidi

- Catalogo dei progettini e prenotazioni: `Progettini_Lista_Prenotazioni.md`
- Guida hands-on Docker su WSL2: `Docker_WSL2_Guida_Esercitazioni.md`
- Guida masquerading nel main namespace: `Namespace_Masquerading_Guida.md`
- Guida hands-on VirtualBox (risorse VM e modalità di networking): `VirtualBox_Risorse_Networking_Guida.md`
- Slide hands-on del corso: `itp-2526-HandsOn.pptx`
