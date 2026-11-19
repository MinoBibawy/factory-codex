# Componenti e attribuzioni

Questa distribuzione include i seguenti materiali. Le copie delle licenze si trovano nella directory LICENSES/.

| Componente nel pacchetto | Origine e versione | Trattamento |
| --- | --- | --- |
| `skills/ponytail`, `skills/ponytail-review` | [Ponytail 5.3.3](https://github.com/DietrichGebert/ponytail/tree/96608e078b2d5ea607c5c3b8b5a54d1c1fba6846), Dietrich Gebert. [Licenza MIT](LICENSES/Ponytail.txt). | Istruzioni upstream. Nel frontmatter di ponytail è stato rimosso il campo argument-hint incompatibile con il validatore Codex. La configurazione Codex aggiunta limita l’attivazione ai ruoli che li richiedono. |
| `skills/poteto-mode` | PStack, Lauren Tan. [Sorgente dei playbook](https://github.com/cursor/plugins/tree/ccb5507cec1546dc88135c1139c811e6c59115ba/pstack/skills/poteto-mode/playbooks). [Licenza MIT](LICENSES/PStack.txt). | Adattamento italiano dei percorsi Bug fix e Perf issue per Factory. Incarichi nativi Codex e consegna locale al coordinatore. |
| `skills/ce-brainstorm`, `skills/ce-plan`, `skills/ce-work`, `skills/ce-code-review` | [Compound Engineering 3.38.2](https://github.com/EveryInc/compound-engineering-plugin/tree/8f7614639e7f3792a6f9337d8742a80a232bd596/skills). [Licenza MIT](LICENSES/Compound-Engineering.txt). | Adattamenti italiani delle quattro fasi utilizzate da Factory. L’ambito comprende incarichi nativi locali con ritorno al coordinatore. |
| `skills/egm-review` | [Elephant Goldfish Model 0.1.1](https://github.com/google/elephant-goldfish-model/tree/70406c4d22cc7ea8299637c2c5b44625c48b3f08), Google. [Licenza Apache-2.0](LICENSES/EGM.txt). | Adattamento italiano del percorso di review uninterrupted e della guida Codex. I file in personas/ e resources/ riproducono i corrispondenti file upstream senza modifiche. |

Le procedure `factory-pr-draft` e di audit interno sono scritte per questa distribuzione. La bozza PR segue i requisiti del progetto per sintesi, evidenze e reversibilità.

## Ispirazione di Factory per Codex

La presa in carico da chat, la coda e il coordinamento dei ruoli si ispirano anche alla [Software Factory v2 di ZazenCodes](https://github.com/zazencodes/zazencodes-season-3/tree/c467603d6d62392cfaae0c07d2f701e99e111443/src/software-factory-claude-code-v2). Il modulo per Claude Code indica [GNU GPL versione 3](https://github.com/zazencodes/zazencodes-season-3/blob/c467603d6d62392cfaae0c07d2f701e99e111443/src/software-factory-claude-code-v2/LICENSE). Il coordinatore Codex, gli script Python, la dashboard e le procedure originali di questo plugin hanno un’implementazione propria. La licenza MIT di Factory per Codex copre i suoi materiali originali. Le componenti incorporate elencate sopra conservano i propri avvisi.
