"""
Régression des verdicts MC (durcissement des 4 scripts de validation).

Principe martelé tout l'arc : on asserte le SIGNE et l'ANCRE (AUC_fonda ≈ 0.85,
Altman), JAMAIS une magnitude de lift (« magnitude non ancrée »). Si une de ces
assertions casse un jour, c'est qu'un verdict de l'audit a bougé — à investiguer.

Les 4 scripts canoniques restent INTACTS (évidence). On en charge seulement les
fonctions via AST (sans exécuter leur Monte-Carlo de niveau module), et on pilote
nous-mêmes avec peu de seeds (le signe est robuste ; la magnitude, on ne la touche pas).

Lent → marqué `slow`, hors suite rapide. Lancer : pytest -m slow
"""
import ast
import pathlib

import numpy as np
import pytest

pytestmark = pytest.mark.slow

VALIDATION = pathlib.Path(__file__).resolve().parent / "validation"


def _load_functions(filename: str) -> dict:
    """Charge UNIQUEMENT imports + définitions de fonctions d'un script canonique
    (drop le code de niveau module qui lance le MC). Fichier laissé intact."""
    src = (VALIDATION / filename).read_text(encoding="utf-8")
    tree = ast.parse(src)
    tree.body = [
        node for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef))
    ]
    namespace: dict = {}
    exec(compile(tree, filename, "exec"), namespace)
    return namespace


def test_tilt_edge_is_survivorship_inflated():
    """Tilt : l'edge sur les survivants > l'edge sur l'univers complet → gonflé.
    SIGNE seulement (l'inflation chiffrée vit dans le script, pas ici)."""
    run = _load_functions("test_tilt_survivorship.py")["run"]
    full, surv = run(seeds=25)
    assert surv.mean() - full.mean() > 0


def test_gate_edge_is_not_survivorship_inflated():
    """Gate ordinal Q+V : inflation NON positive (signe opposé au tilt) → robuste."""
    run = _load_functions("test_gate_survivorship_v2.py")["run"]
    _rules, _edgeF, infl, *_ = run(seeds=25)
    assert np.mean(infl["Q+V"]) < 0.0


def test_shield_balance_sheet_beats_price_with_anchor():
    """Bouclier structurel : ancre AUC_fonda ~0.85 (Altman) ET combo bat le prix
    quand le prix est bruité. Signe du lift, JAMAIS sa magnitude."""
    ns = _load_functions("test_shield_structural.py")
    F, D, L, _V = ns["pooled"](noise_f=3.6, noise_p=0.20, seeds=4)
    af, ad, ac = ns["aucs"](F, D, L)
    assert 0.80 <= af <= 0.90   # ANCRE
    assert ac > ad              # SIGNE du lift incrémental, pas sa taille


def test_shield_fixed_bucket_lift_positive_and_deflated_vs_biased():
    """Bucket cheap par valo indépendante : lift positif (signe) ET plus petit que
    l'ancien bucket biaisé par -dd (déflation par levée de range restriction).
    Direction seulement, aucune valeur de lift assertée."""
    ns = _load_functions("test_shield_fixed_bucket.py")
    F, D, L, V = ns["pooled"](seeds=4)

    m = V >= np.percentile(V, 66.7)            # bucket corrigé (valo indépendante)
    _af, ad, ac = ns["aucs"](F[m], D[m], L[m])
    assert ac > ad

    mB = D >= np.percentile(D, 66.7)           # ancien bucket biaisé (par -dd)
    _af2, ad2, ac2 = ns["aucs"](F[mB], D[mB], L[mB])
    assert (ac - ad) < (ac2 - ad2)
