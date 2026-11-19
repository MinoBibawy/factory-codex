# Verifica dell’impatto prima delle review

Esegui `Q check ID --risk low --small` con i livelli effettivamente previsti (`--ui`, `--backend` o entrambi). Il gate esamina il diff tra la base registrata quando il job è stato assegnato e il commit pulito che sarà sottoposto ai test. Considera anche i file cancellati e il vecchio percorso dei file rinominati.

Il gate riconosce le convenzioni comuni di frontend e backend e verifica alcune dichiarazioni di endpoint, RPC e tabelle nel contenuto precedente e corrente dei file modificati. Questo include il cambio di risposta sotto un decoratore di rotta rimasto identico. Contratti API, persistenza, autorizzazioni, componenti condivisi, dipendenze, percorsi sconosciuti o livelli imprevisti fanno passare al percorso completo con rischio almeno medio. Il gate esegue i controlli comuni e tutte le suite per livello configurate, e riapre gli incarichi di review necessari. I dettagli del round in dashboard spiegano il motivo e mostrano un percorso rappresentativo per ciascuna causa. In un progetto senza Git, l’impronta locale protegge la versione verificata e il gate adotta il percorso completo.

Per le convenzioni specifiche del repository puoi aggiungere al piano locale dei controlli un campo come:

```json
{"impact_paths":{"ui":["packages/console/*"],"backend":["services/pricing/*"],"full":["shared-sdk/*"]}}
```

I pattern si riferiscono ai percorsi dalla radice del repository, distinguono maiuscole e minuscole e `*` può comprendere le sottocartelle. Sono additivi. Per esempio un file con una migrazione nel percorso di un backend personalizzato fa comunque scattare la verifica completa. Per API e autorizzazioni con convenzioni proprie, registra i loro percorsi sotto `full`. L’analisi delle righe riconosce dichiarazioni comuni e l’intake resta responsabile degli effetti semantici e indiretti nei componenti conosciuti.

`F show ID` espone `quality.impact.declared`, `detected` e `reasons` per il round in cui è stato valutato il percorso piccolo. Il rischio rimane almeno quello già accertato nelle riprese dello stesso job. Se riprendi una vecchia review ridotta priva della valutazione dell’impatto, ripeti il gate prima della consegna.
