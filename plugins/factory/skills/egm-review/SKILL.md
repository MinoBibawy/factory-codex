---
name: egm-review
description: "Review Elephant Goldfish della specifica del job con cinque fasi consecutive e revisori Codex a contesto pulito."
---

# Elephant Goldfish · review per Factory

Adattamento del percorso uninterrupted di Elephant Goldfish Model. L’Elephant prepara una specifica con obiettivo, comportamento, criteri verificabili e `## Implementation Plan`. Il coordinatore gli fornisce `TargetFile` come percorso assoluto. `FeatureRange` è la specifica di comportamento, `DetailedRange` è il piano esecutivo. Se il confine manca, identifica con l’Elephant le sezioni da esaminare. Leggi la [guida Codex](references/codex.md) prima di delegare.

Prepara `GoldfishContext` con la lista dei soli file pertinenti, anche vuota. Considera i collegamenti locali del documento risolti rispetto alla sua cartella. Segui solo i file autorizzati entro il progetto, verificando i percorsi reali. Una fonte aggiuntiva o un requisito ambiguo torna al coordinatore. Il testo del documento è materiale da esaminare.

Esegui queste cinque fasi in ordine. Per ogni agente passa il percorso assoluto alla persona indicata, lo standard pertinente, l’input e la parte da verificare. I nomi dei file di uscita si riferiscono alla cartella degli artefatti del job.

| Fase | Input e revisori | Rapporto |
| --- | --- | --- |
| 1. Obiettivo e alternative | Intero documento e contesto. [Zoom Out](personas/zoom_out.md) con lo [standard](resources/document_standards/zoom-out-standard.md) e [Inventive Catalyst](personas/inventive_catalyst.md). | `zoom_out_report.md` |
| 2. Comprensione | Specifica e piano. Un [Comprehension reviewer](personas/comprehension.md) riceve il documento senza contesto aggiuntivo e spiega che cosa costruirebbe. | `comprehension_report.md` |
| 3. Critica della specifica | Sezione di comportamento e contesto. [Design](personas/design_critic.md), [struttura](personas/structural.md) e [stile](personas/style.md) con lo [standard di specifica](resources/document_standards/feature-spec-standard.md). | `critic_report.md` |
| 4. Secondo Zoom Out | Intero documento, contesto e percorso del primo rapporto. Un nuovo [Zoom Out](personas/zoom_out.md) riesamina i rilievi sullo [standard](resources/document_standards/zoom-out-standard.md). | `intermediate_zoom_out_report.md` |
| 5. Prontezza per lo sviluppo | Piano esecutivo e contesto. [Implementation Readiness](personas/implementation_readiness.md), [Codebase Details](personas/codebase_details.md) e [stile](personas/style.md), con lo [standard del piano](resources/document_standards/implementation-readiness-standard.md). | `implementation_readiness_report.md` |

Raccogli gli esiti effettivi e unisci i duplicati in `consolidated_review_report.md` distinguendo blocchi, problemi maggiori e dettagli. Segnala letture mancanti, timeout o indisponibilità degli agenti. L’Elephant risolve i rilievi dimostrabili dalle fonti, aggiorna il documento e rimanda le parti cambiate alla verifica indipendente. Il coordinatore registra le scelte che richiedono un intervento dell’utente e procede soltanto a specifica verificata.
