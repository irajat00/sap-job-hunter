"""
Synonym expansion for "smarter search" -- rule-based (data-driven
dict), not embeddings-based semantic search (no paid API in this
project's budget). Expands a search term into itself plus known
synonyms/related phrases before matching, e.g. "SAP PP" also matches
titles saying "Production Planning" or "Manufacturing Consultant".
"""
SYNONYM_GROUPS = [
    ["sap pp", "production planning", "manufacturing consultant", "pp consultant", "s/4 pp", "s4 pp"],
    ["sap qm", "quality management", "qm consultant", "inspection lot"],
    ["hrbp", "hr business partner", "people partner", "talent partner"],
    ["hr manager", "human resources manager"],
    ["talent acquisition", "recruiter", "recruitment", "talent sourcing"],
    ["learning & development", "l&d", "training & development"],
]

_LOOKUP = {}
for group in SYNONYM_GROUPS:
    for term in group:
        _LOOKUP[term] = group


def expand_search_terms(query: str) -> list[str]:
    """Returns [query] plus any known synonyms/related terms, all lowercase."""
    if not query:
        return []
    q = query.strip().lower()
    return sorted(set(_LOOKUP.get(q, [q]) + [q]))
