---
name: poteto-mode
description: "Playbook Poteto adattati a Codex per la presa in carico, la correzione e la verifica di bug e regressioni di prestazioni affidati da Factory."
---

# Poteto Mode per Factory

Adattamento dei playbook Bug fix e Perf issue di PStack per un incarico locale di Factory. Usa il ramo corrispondente. Identifica il job e segui le regole del repository.

**Bug fix.** Fissa l’ingresso esatto, l’effetto osservato e l’atteso prima di intervenire. Ripeti il caso sulla superficie segnalata, con dati di prova, e conserva comando, risultato e versione. Se l’ambiente manca, descrivi che cosa impedisce la verifica. Restringi le cause usando i passaggi effettivi del programma. Per ogni ipotesi scegli una prova che la possa smentire. Scrivi o individua un test che fallisca sul difetto osservato. Verifica il motivo del fallimento. Cambia il punto da cui nasce il comportamento e riesegui test e caso originale sulla stessa superficie.

**Perf issue.** Registra scenario, ambiente, volume, metrica, obiettivo e una misura ripetibile. Ripeti la misura e annota la variabilità prima della modifica. Usa un profilo o un contatore per individuare il lavoro costoso. Parti dal lavoro superfluo, ripetuto o eseguito troppo presto. Cambia una cosa per volta. Ripeti le misure con gli stessi dati e verifica anche la correttezza. Riporta valori osservati, unità, differenza e limiti. Una variazione entro il rumore lascia aperto il risultato.

L’agente di intake consegna il caso e la prova al coordinatore. Lo sviluppatore usa il playbook per la fix. A chiusura l’agente di intake confronta il valore misurato sul commit in review con l’atteso originale. Per una verifica qualità controlla anche i casi limite interessati, le responsabilità dei chiamanti e la semplicità della soluzione. Ritorna al coordinatore con prova, esito e limiti. Il coordinatore gestisce la consegna e gli eventuali consensi.
