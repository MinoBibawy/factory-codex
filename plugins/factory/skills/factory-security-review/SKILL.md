---
name: factory-security-review
description: Audit difensivo indipendente del diff finale di Factory. Usalo per verificare confini di fiducia, protezione dei dati e controlli di accesso e produrre prove sul commit in revisione.
---

# Audit difensivo di Factory

Ricevi l’ID del job, il commit o l’impronta locale, il round, il perimetro e i criteri di accettazione. Conferma che la revisione sia quella assegnata e che l’autore della modifica sia un’altra persona o un altro agente.

1. Leggi il diff e i chiamanti pertinenti. Individua quali input o identità attraversano un confine di fiducia, quali dati vengono letti o conservati e con quali permessi. Per documentazione o logica senza effetti esterni, indica perché l’esposizione è limitata.
2. Segui ciascun percorso coinvolto nel codice. Dove pertinenti, controlla autorizzazione lato servizio, validazione prima dell’uso, parametri di query e processi, destinazione e permessi dei file, gestione di segreti e dati personali in log e dashboard. Per nuove dipendenze controlla provenienza e cambiamenti dei permessi. Registra file e riga per ogni conclusione sostanziale.
3. Verifica i controlli difensivi con i test del progetto, dati sintetici e risorse locali autorizzate. Esegui soltanto comandi verificati. Riporta comando, esito e limiti senza includere dati privati. Se mancano condizioni per una verifica necessaria, indica cosa occorre e lascia il controllo aperto.
4. Per un rilievo documenta la conseguenza concreta, la gravità motivata e la correzione minima. Restituisci il verdetto `changes` se serve una modifica. Dopo la correzione ricontrolla il punto sul nuovo commit. Assegna `pass` solo quando le prove sostengono il giudizio sul diff. La mancanza di uno strumento o di accesso non equivale a un esito positivo.

Consegna al coordinatore identità del revisore, revisione, round, verdetto, prove e limiti. Per il ruolo `security` la ricevuta registra la skill `factory-security-review`.
