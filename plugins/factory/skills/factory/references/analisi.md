# Prove di una proposta e ripresa della decisione

Nei comandi F è `python3 -B <skill-factory>/scripts/factory.py`, P è `python3 -B <skill-factory>/scripts/proposal.py` e R è `python3 -B <skill-factory>/scripts/resume.py`. Eseguili dal progetto del job. Sostituisci i nomi di esempio con i dati del caso reale.

## Registrare ciò che è stato provato

Usa `F add ID "titolo" --proposal` per «trova una soluzione» e `--design-only` per una diagnosi. Dopo claim e intake, l’analista salva il rapporto locale in `artifacts/ID/analysis.md` accanto alla dashboard. Indica gli input e i risultati osservati del caso originale e di un controllo che scopra una soluzione sbagliata. Se provi una modifica su copia, conserva separati i file del progetto. Scegli una sola delle seguenti registrazioni:

```sh
P record ID WORKER pending --source docs/contract.md --reason "Manca un campione autorizzato del partner"
P record ID WORKER fixture --source catalog.py --source docs/contract.md --case "ID 00123: prima assente, su copia restituisce lampada" --control "ID 00999: su copia resta assente"
P record ID WORKER commit --sha SHA_COMPLETO --source catalog.py --case "Caso originale eseguito sul commit: risultato atteso" --control "Caso vicino eseguito sul commit: risultato atteso"
```

Una ricevuta attesta il lavoro eseguito dall’agente. Registra `commit` soltanto dopo entrambe le prove sul worktree pulito della revisione indicata. Un job di proposta non autorizza un commit di implementazione. Per una prova impossibile o fallita conserva l’esito nel rapporto e usa `pending` con il limite o la prossima verifica. Chiudi il job quando hai comunque consegnato una proposta motivata. Se manca una scelta necessaria alla proposta, apri una domanda.

Elenca con `--source` i file che sostengono la raccomandazione, usando percorsi relativi nel progetto. Usa `--external "decisione formato v2"` per una fonte esterna autorizzata. Preferisci un’etichetta priva di dati riservati. Il comando non contatta Obsidian o Confluence. Per un vault interno al progetto puoi registrare un file relativo consentito. La chiusura `F move ID WORKER ok` verifica che rapporto e fonti locali siano ancora quelli registrati. Se una fonte è cambiata, aggiorna il rapporto e ripeti le prove interessate prima di registrare di nuovo l’esito.

## Implementare in seguito

Crea un job separato con `--after ID_PROPOSTA` dopo l’ordine di sviluppare. Dal job figlio già assegnato, esegui `P status ID_FIGLIO`. Anche R segnala la prossima azione con `recheck_proposal`. Il risultato di status associa a ogni proposta le sole fonti da ricontrollare. Il confronto usa la revisione del figlio. Una fonte esterna richiede un controllo esplicito anche quando il file del rapporto è identico.

Per ogni elemento rileggi la fonte attuale e usa la chiave e l’impronta restituite da status:

```sh
P recheck ID_FIGLIO WORKER ID_PROPOSTA "file:docs/contract.md" --observed IMPRONTA --evidence "La revisione aggiorna gli esempi; il formato richiesto resta invariato"
P recheck ID_FIGLIO WORKER ID_PROPOSTA "external:decisione formato v2" --observed manual --evidence "Riletta la decisione autorizzata; si applica a v2"
```

Se la prova del padre era su un commit preciso e il figlio ha un altro SHA, riesegui caso e controllo sul checkout pulito del figlio. Per la chiave `commit` usa `P recheck ID_FIGLIO WORKER ID_PROPOSTA commit --observed SHA_FIGLIO --evidence "Motivo del ricontrollo" --case "Caso originale e risultato misurato" --control "Caso di controllo e risultato misurato"`. La prova del padre resta storica.

Per un file rimosso chiarisci quale fonte lo sostituisce e se la raccomandazione è ancora valida. Se una scelta è cambiata, torna all’analisi. Una fonte necessaria inaccessibile mantiene il lavoro in feedback. Se il file del rapporto manca, recuperalo prima di proseguire. `F move ID_FIGLIO WORKER build` ripete il controllo sotto il lock della coda. I vecchi job privi di ricevuta restano leggibili: verifica il loro rapporto manualmente prima di riusarlo.

## Domande che sopravvivono a una nuova chat

Durante analisi o sviluppo, apri una domanda quando serve una scelta dell’utente. Riusa la stessa chiave se ritenti la stessa operazione. Invia la domanda in chat con le conseguenze delle alternative e conserva il riferimento restituito:

```sh
F ask ID WORKER formato-v2 "I codici di v1 devono restare validi in v2? Accettarli estende la compatibilità; rifiutarli mantiene il contratto attuale."
R ID
F answer ID WORKER RIFERIMENTO "Risposta effettiva dell'utente"
```

L’agente registra la risposta solo dopo averla ricevuta e collegata a quella domanda. Se più domande possono corrispondere, chiarisci quale intende l’utente. Dopo un’interruzione consulta R: `await_answer` indica una domanda aperta. Con `resume_decision` la risposta è già salvata: appena si libera un posto ripeti lo stesso `answer` con i dati registrati. Non richiedere nuovamente la decisione. Per aggiungere una nota al vault, pubblicare o integrare una PR segui le rispettive autorizzazioni.
