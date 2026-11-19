---
name: ce-work
description: "Esecuzione locale di un piano Compound Engineering in modalità return-to-caller per Factory."
---

# Compound Engineering · sviluppo

Adattamento per Factory con ritorno al coordinatore. Leggi richiesta, piano e vincoli di progetto nel worktree assegnato. Controlla lo stato iniziale e i test che proteggono i chiamanti. Scegli il prossimo passo i cui prerequisiti risultano soddisfatti. Per cambi di logica verifica il test RED e il motivo, applica la modifica minima e verifica GREEN. Per refactoring a comportamento invariato misura il risultato prima e dopo. Segui le regole del progetto per test e commit.
 
Procedi per risultati osservabili, registra verifiche e aggiorna solo la documentazione direttamente interessata. Se una scoperta cambia il contratto o la decisione dell’utente, torna al coordinatore con la prova e la domanda. A fine sviluppo restituisci elenco sintetico delle modifiche, revisione, test eseguiti, esiti e limiti. Il coordinatore gestisce review, audit, conferme di pubblicazione e chiusura.
