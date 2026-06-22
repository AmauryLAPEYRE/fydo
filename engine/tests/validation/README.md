# Évidence de validation (l'arc, figé)

Ces scripts sont la **preuve chiffrée** issue de l'audit croisé à deux instances. Ils ne
font PAS partie du build prod — ce sont des artefacts d'audit + régression, lancés à la
demande. Ils figent *pourquoi* le moteur a la forme qu'il a (SPEC §0).

| Fichier | Prouve | Verdict |
|---|---|---|
| `test_tilt_survivorship.py` | la survivance gonfle l'edge du tilt drawdown au-delà de l'edge mesuré | tilt **falsifié → retiré** |
| `test_gate_survivorship_v2.py` | le gate ordinal Q+V n'est PAS gonflé (signe opposé au tilt) | gate **robuste** |
| `test_shield_structural.py` | le bilan ajoute un AUC incrémental sur le prix (santé latente Merton) | bouclier **mord** |
| `test_shield_fixed_bucket.py` | section 3 corrigée : bucket cheap par valo indépendante du drawdown (range restriction levée) | lift +0.089 (moitié du +0.165 gonflé) |

## Dépôt des fichiers canoniques

Les 4 `.py` ci-dessus sont **déposés tels quels par l'humain** (versions UTF-8 canoniques),
PAS régénérés ici — même principe que `SPEC_QV_ENGINE_FINAL.md` : re-transcrire rouvrirait
une divergence. Cible : `engine/tests/validation/`.

## Lancer

Nécessite `scikit-learn` (deux scripts utilisent `roc_auc_score` / `LogisticRegression`) :

```
pip install -e ".[dev]"
PYTHONUTF8=1 python tests/validation/test_tilt_survivorship.py
```

Durcissement prévu (Step 3) : envelopper les nombres-clés (ΔSharpe inflation, lift AUC,
signe du gate) dans des `assert` pour en faire de vrais tests de non-régression pytest,
au lieu de scripts à print. Le MC du bouclier devient alors régression du `distress.py`.
