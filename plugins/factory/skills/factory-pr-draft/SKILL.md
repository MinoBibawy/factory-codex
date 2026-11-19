---
name: factory-pr-draft
description: "Prepara una descrizione locale di pull request con modifica, confronto prima e dopo e conseguenze di un ripristino."
---

# Bozza di pull request

Raccogli dal coordinatore repository, ramo sorgente, destinazione, commit verificato, diff ed evidenze del job. Leggi il modello PR del progetto e rispettane lingua e campi. Salva la bozza nell’artefatto assegnato al job.

Descrivi il cambiamento dal punto di vista dei chiamanti. Un esempio di input e output, un diff di poche righe o uno schema può renderlo più chiaro. Nelle prove riporta lo stesso caso prima e dopo la modifica, insieme al comando usato. Se manca una misura, indica quale parte resta da verificare. Spiega quali componenti o utenti ricevono il cambiamento, se è possibile annullarlo con un revert e se rimangono effetti sui dati.

Restituisci il percorso locale della bozza e gli elementi per il riepilogo dell’operazione. Il coordinatore presenta in chat quattro punti con modifica, repository, rami e commit e raccoglie i consensi distinti a push e merge.
