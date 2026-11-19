# Subentro su un rilievo aperto

Ogni nuovo verdetto positivo, singolo o raggruppato, indica in `--agent` l'ID del revisore che ha eseguito la verifica. I verdetti già salvati restano leggibili. Il revisore deve essere indipendente dal titolare del lavoro e da chi ne ha curato lo sviluppo.

Dopo un'interruzione consulta `resume.py ID`. Un rilievo aperto torna al revisore assegnato. Prova a riagganciarlo e verifica lo stato negli strumenti nativi: un incarico ancora attivo va atteso. Se la sessione è conclusa o la ripresa fallisce definitivamente, conserva un riscontro breve e assegna un nuovo agente nativo indipendente con il modello ereditato. Se mancano riscontri o un sostituto disponibile, porta il lavoro in feedback.

Quando la versione corretta ha superato i controlli, il titolare registra il subentro sul ruolo ancora in attesa:

```text
Q handover ID RUOLO --worker TITOLARE --from-agent PRECEDENTE --to-agent SOSTITUTO --sha REV --round N --reason "sessione conclusa, tentativo di riaggancio e relativo esito"
```

Leggi `F show ID` per riprendere tutti gli scenari del rilievo, la verifica dello sviluppatore e lo stato attuale. Passali al sostituto insieme alla skill del ruolo. Il sostituto deve ripetere personalmente tutti gli scenari sulla revisione indicata e restituire input, esito e comando o artefatto della propria prova. Un `pass` richiede sia la prova della correzione registrata con `Q remedy` sia la controprova del revisore. Ogni nuovo `changes` segue il ciclo di correzione. La cronologia `review_handovers` conserva ruolo, entrambi gli agenti, motivo, titolare, round, piano e revisione anche dopo la chiusura.

Il subentro riguarda il revisore di un rilievo. Per la riprova finale del bug continua a valere l'assegnazione originaria della presa in carico.
