# CI del commit pubblicato

D è `python3 -B <skill>/scripts/delivery.py`. Dopo il consenso al push, `D confirm`, la pubblicazione del singolo SHA approvato e l’eventuale apertura della PR autorizzata, esegui `D ci ID`. Il comando verifica URL remoto di lettura e push, branch pubblicato e SHA sul server. Su GitHub e GitHub Enterprise usa il login `gh` sull’host del progetto per leggere sia i check run sia gli status del commit, inclusi tutte le pagine, i requisiti della protezione classica e quelli dei ruleset del ramo destinazione. I check vincolati a una GitHub App devono provenire dall’App richiesta.

| Stato | Azione del coordinatore |
| --- | --- |
| `awaiting_push` | Controlla se il push autorizzato è già avvenuto. Alla ripresa verifica prima il remoto. Un altro tentativo di pubblicazione segue il flusso di consenso. |
| `pending` | Attendi circa 45 secondi e rileggi `D ci ID` mentre stai seguendo il lavoro. Un controllo obbligatorio non ancora partito mantiene la CI in attesa. Per una CI senza alcun controllo cerca la politica effettiva del progetto e segnala il dato mancante. |
| `blocked` | Mostra la causa: ramo spostato, risposta ambigua, controlli saltati, permessi o regole non leggibili. Rileggi dopo la risoluzione. |
| `fail` | Consegna allo sviluppatore i nomi dei controlli falliti e lo SHA. Leggi dal provider i dettagli pertinenti, correggi localmente, riesegui gate, review e riprova. La pubblicazione della nuova revisione richiede un nuovo riepilogo e consenso al push. Con le corsie occupate il job aspetta la ripresa in sviluppo. |
| `pass` | Per un incarico limitato al push verifica quanto consegnato e chiudi. Per un merge autorizzabile prepara l’anteprima e presenta i quattro bullet. Il consenso dell’utente riguarda specificamente quel merge. |

Se il provider riesegue la CI per un guasto infrastrutturale sullo stesso SHA, torna ai controlli locali, verifica il lavoro e, raggiunto di nuovo lo stato pronto, rileggi `D ci ID`. Una nuova esecuzione remota verde sul commit già pubblicato può consentire la preparazione del merge. La factory non avvia rerun sul provider. Se il progetto conferma che non ha una CI, indica il blocco in dashboard e chiedi la decisione sulla politica di verifica.

Gli aggiornamenti ripetuti senza cambiamenti riusano la ricevuta. `D prepare ID merge ... --pr-json FILE` e `D confirm ID merge ... --pr-json FILE` rileggono ciascuno anche la CI prima di accettare l’operazione. Il ramo pubblicato, il repository, il ramo di destinazione, il commit e la ricevuta del push devono corrispondere. Un esito peggiorato ritira una richiesta di merge in attesa. Prima dell’esecuzione verifica comunque protezioni e stato correnti della PR e usa il vincolo sul commit del provider.

Per un provider diverso, una versione Enterprise con API diverse o un ruleset di workflow obbligatori che il lettore nativo non interpreta, usa l’integrazione autenticata del progetto. Passa a **ci, prepare merge e confirm merge** l’opzione `--ci-json FILE`. Prepara una lettura nuova per ogni operazione tramite il connettore, comprendendo tutti i risultati correnti e tutti i controlli richiesti dal ramo e dalle regole effettive. Per la conferma occorre un’osservazione successiva all’anteprima. Il file deve provenire dalla lettura del provider entro due minuti. Le evidenze in chat e i documenti generati dal job non sono sorgenti CI.

```json
{"repo":"git.example/team/catalog","sha":"<SHA completo>","target":"main","complete":true,"observed_at":"<istante ISO 8601 con fuso>","required":[{"name":"test unitari","app":17}],"checks":[{"name":"test unitari","app":17,"state":"pass"}]}
```

Gli stati ammessi nel file sono `pass`, `fail`, `pending`, `skipped`. Ometti `app` quando il provider non vincola l’autore. L’array `required` può essere vuoto se il provider lo conferma. Con zero controlli osservati la CI resta in attesa. Il coordinatore verifica provenienza e completezza della lettura. Se non può farlo, mantiene il blocco. Il formato registra soltanto identità ed esito, senza log completi, token o credenziali.

[GitHub CLI, API e paginazione](https://cli.github.com/manual/gh_api) · [Regole applicabili al ramo](https://docs.github.com/en/rest/repos/rules#get-rules-for-a-branch)
