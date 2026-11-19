# Factory per Codex

Factory prende in carico un problema dalla chat del progetto, coordina sviluppo e revisione e mostra una dashboard con lavori in corso, richieste di feedback, esiti, PR e artefatti. Il plugin comprende il coordinatore e gli specialisti necessari per una fix locale. Le regole e i comandi di test del progetto provengono dai suoi file `AGENTS.md`.

## Installazione locale

Servono Codex con supporto ai plugin e agli agenti nativi, Git e Python 3 con `fcntl`. La piattaforma collaudata è macOS arm64. I comandi della coda sono stati provati con Python 3.9.6 e 3.14.7. Windows nativo richiederebbe un adattamento dei lock di processo. Su Linux o WSL verificare coda e worktree prima di adottare il plugin.

Estrai il pacchetto in una cartella stabile. Apri il terminale nella cartella che contiene questo README ed esegui questa riga:

```sh
codex plugin marketplace add "$PWD" && codex plugin add factory@factory-tools
```

Apri una chat del progetto e seleziona **Factory** nel selettore delle skill. Il nome qualificato è `$factory:factory`, utile anche se hai installata una versione precedente. I file delle skill si installano insieme e i progetti mantengono i loro strumenti di sviluppo. La credenziale per la chat Codex e la disponibilità degli agenti dipendono dalla tua installazione.

## Primo lavoro

Nella chat in cui hai già descritto il problema scrivi, per esempio:

```text
Quando salvo un’etichetta restano gli spazi finali. L’analisi è nel messaggio precedente. /factory risolvi
```

`/factory` è la convenzione testuale interpretata dalla skill. Se il client non la seleziona automaticamente, scegli `$factory:factory` e invia lo stesso messaggio. Factory crea un job e apre la dashboard locale. Con `/factory stato` rivedi la coda. Con `/factory riprendi` riparti dalle prove già registrate. Un profilo privo della capacità di delega può consultare lo stato e mostra quale incarico attende un agente.

| Se chiedi… | Factory usa… |
| --- | --- |
| Una fix o una regressione | Poteto per presa in carico e diagnosi, Ponytail per lo sviluppo, controlli reali del progetto, review codice, audit difensivo e review qualità. Il caso originale viene riprovato dopo la correzione. |
| Una modifica con scelte aperte | Le fasi Compound pertinenti e, per le decisioni previste, Elephant Goldfish con revisori indipendenti. |
| Una bozza PR | Lo specialista incluso prepara sintesi, prove prima/dopo e rischio del merge. Una bozza locale si può leggere dalla dashboard. |
| Una consegna remota | Il coordinatore verifica repository, branch e commit. I consensi per push e merge sono separati. La CI GitHub richiede `gh` autenticato con accesso in lettura. Per altri provider serve una fonte equivalente dei controlli. |

## Dati e permessi

Esegui Factory in un progetto attendibile. I comandi dei test vengono eseguiti nel worktree con i permessi del processo. Se i test provengono da terzi, usa un ambiente isolato senza credenziali non necessarie e controlla script e configurazioni prima di avviarli. Nelle ricevute rimangono gli argomenti dei comandi: evita token o altri segreti nella riga di comando. Le anteprime di push e merge leggono il remoto configurato.

La coda, le prove e la dashboard sono conservate in `factory/` nella directory Git comune, oppure in `.factory/` per un progetto senza Git. Gli artefatti possono contenere informazioni del progetto. Se devi condividere un risultato, scegli i singoli file da condividere.

## Rimozione

```sh
codex plugin remove factory@factory-tools
```

La rimozione riguarda il plugin. Coda e prove appartengono al progetto.

## Origine e licenze

Il materiale originale di Factory per Codex è distribuito con [licenza MIT](plugins/factory/LICENSE). Le condizioni delle componenti incorporate e le modifiche per Codex sono documentate nelle [attribuzioni](plugins/factory/THIRD_PARTY.md). Factory per Codex trae ispirazione dalla [Factory v2 di ZazenCodes alla revisione consultata](https://github.com/zazencodes/zazencodes-season-3/tree/c467603d6d62392cfaae0c07d2f701e99e111443/src/software-factory-claude-code-v2).
