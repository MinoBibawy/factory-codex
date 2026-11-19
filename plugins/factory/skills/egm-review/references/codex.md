# Adattamento Codex

Usa come radice la directory che contiene il file SKILL.md di egm-review. Le persone e gli standard si trovano nelle sue directory personas/ e resources/document_standards/. Ricava i percorsi assoluti reali prima della delega. Archivia i rapporti nella directory locale del job assegnata da Factory.

Ogni Goldfish opera in un contesto nuovo. Con la delega nativa usa `fork_turns: "none"` oppure `fork_context: false` secondo la firma disponibile. Invia la persona, la sezione da leggere, lo standard applicabile e i soli file di contesto consentiti per quella fase. La fase di comprensione riceve solo la specifica con il piano e la propria persona. Escludi la conversazione dell’Elephant, le ipotesi private e le risposte che il revisore deve ricavare dal documento.

Il coordinatore può distribuire i ruoli direttamente. Se gli slot sono limitati, avvia nuovi revisori in sequenza. Conserva i rapporti restituiti. Ogni agente indica quali file ha effettivamente letto e quali prove sostengono i rilievi. Se l’host non offre un contesto isolato o una fonte obbligatoria è illeggibile, registra il problema in Factory. Opera sui materiali locali autorizzati e secondo le istruzioni del progetto.
