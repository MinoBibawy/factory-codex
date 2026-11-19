"""Valuta il perimetro di un percorso piccolo con il diff completo dalla base del job."""
from fnmatch import fnmatchcase
from pathlib import PurePosixPath
import re


# Espressione POSIX applicata ai blob Git dei file toccati.
BOUNDARY_LINES = (r'^[[:space:]]*(@?(app|api|router|blueprint)\.(get|post|put|patch|delete|route|use)\('
                  r'|@(Get|Post|Put|Delete|Patch|Request)(Mapping)?\(|rpc[[:space:]]+'
                  r'|ALTER[[:space:]]+TABLE|CREATE[[:space:]]+TABLE|DROP[[:space:]]+TABLE)')


def path_impact(name, rules):
    path = PurePosixPath(name)
    tokens = set(re.findall(r'[a-z0-9]+', re.sub(r'([a-z])([A-Z])', r'\1 \2', name).lower()))
    matches = {kind for kind, patterns in rules.items() if any(fnmatchcase(name, p) for p in patterns)}
    layers = matches & {'backend', 'ui'}
    if tokens & {'ui', 'frontend', 'components', 'views', 'styles'} or path.suffix.lower() in {
            '.tsx', '.jsx', '.vue', '.svelte', '.css', '.scss'}:
        layers.add('ui')
    if tokens & {'backend', 'server', 'api', 'controllers', 'endpoints', 'migrations'}:
        layers.add('backend')

    if tokens & {'auth', 'authentication', 'authorization', 'permissions', 'oauth', 'acl', 'secrets',
                 'security', 'secret', 'rbac', 'jwt', 'login', 'credentials', 'password', 'policies',
                 'schema', 'schemas', 'db', 'database', 'persistence', 'migration', 'migrations'} or path.suffix.lower() == '.sql':
        return layers, 'Sicurezza o dati persistenti'
    if tokens & {'api', 'contracts', 'contract', 'openapi', 'swagger', 'graphql', 'protobuf', 'routes',
                 'endpoints'} or path.suffix.lower() == '.proto':
        return layers, 'Possibile modifica di un contratto'
    if path.name.lower() in {'package.json', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 'dockerfile',
                             'pyproject.toml', 'go.mod', 'cargo.toml', 'pom.xml', 'requirements.txt'}:
        return layers, 'Dipendenze o configurazione della build'
    if tokens & {'shared', 'common', 'infra', 'infrastructure', 'workflow', 'workflows'} or 'full' in matches:
        return layers, 'Componente condiviso o trasversale'
    if not layers and path.suffix.lower() not in {'.md', '.rst'}:
        return layers, 'Percorso non classificato'
    return layers, ''


def assess(names, declared, rules, has_git, boundary_files):
    observed = set()
    reasons = {}
    if not has_git:
        reasons['Base Git assente per confrontare il perimetro'] = ''
    for name in names:
        layers, reason = path_impact(name, rules)
        if name in boundary_files:
            layers.add('backend')
            reason = reason or 'File modificato con endpoint, RPC o dichiarazione di tabella'
        observed.update(layers)
        if reason:
            reasons.setdefault(reason, name)
        extra = sorted(layers - declared)
        if extra:
            reasons.setdefault('Livello fuori dal perimetro dichiarato (' + ', '.join(extra) + ')', name)
    if len(observed) > 1:
        reasons.setdefault('Modifica che coinvolge frontend e backend', '')
    return dict(declared=sorted(declared), detected=sorted(observed), reasons=[
        (f'{reason} · {name}' if name else reason).encode('utf-8', 'backslashreplace').decode('utf-8')
        for reason, name in reasons.items()])
