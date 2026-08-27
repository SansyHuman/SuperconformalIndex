# N=2 gauge-anomaly checker

`check_n2_anomalies.py` checks finite semisimple gauge algebras whose simple
factors have Cartan type `A_r`, `B_r`, `C_r`, `D_r`, `E6`, `E7`, `E8`, `F4`,
or `G2`. Dynkin labels use Bourbaki numbering.

The corresponding compact gauge group is assumed to be simply connected:
`A_r` means `SU(r+1)`, `B_r` and `D_r` mean Spin groups, and `C_r` means
`Sp(r)`. Global quotients are outside the current scope.

## Runtime

The checker requires SageMath and was verified with SageMath 10.7. In PyCharm,
select the configured Sage Conda environment as the project interpreter. From
a terminal, use Sage's Python launcher so that all Sage runtime paths are set.
For example:

```bash
sage -python anomalies/check_n2_anomalies.py anomalies/example_e6.json
sage -python anomalies/check_n2_anomalies.py anomalies/example_a1_g2_product.json
```

A single simple factor uses:

```json
{
  "algebra": "E6",
  "hypermultiplets": [
    {"representation": "fundamental", "number": 4, "kind": "full"}
  ]
}
```

A product uses an `id` for each factor and an external tensor-product
representation for each hypermultiplet:

```json
{
  "gauge_groups": [
    {"id": "left", "algebra": "C3"},
    {"id": "right", "algebra": "G2"}
  ],
  "hypermultiplets": [
    {
      "representations": {
        "left": "fundamental",
        "right": "fundamental"
      },
      "kind": "full"
    }
  ]
}
```

Representations can instead be specified by a Dynkin-label list. Common names
include `singlet`, `fundamental`, `antifundamental`, and `adjoint`; the
classical families additionally support their applicable `vector`, `spinor`,
`cospinor`, `symmetric`, and `antisymmetric` names. `fundamental_k` selects
fundamental weight number `k` directly.

SageMath's `CartanType`, `RootSystem`, and `WeylCharacterRing` provide the root
data, dual Coxeter numbers, representation dimensions and duals, and
Frobenius-Schur indicators. The checker uses these to compute exact quadratic
Casimirs and Dynkin indices. It then checks representation validity, the
perturbative gauge anomaly implied by N=2 hypermultiplets, the conventional
mod-two Witten anomaly for `A1` and `C_r` (including the isomorphic `B2` case),
and each factor's one-loop N=2 beta function. Pure flavor anomalies and global
anomalies that depend on a non-simply-connected quotient are not tested.

Run the tests with:

```bash
sage -python -m unittest discover -s test -p 'test_*.py' -v
```

## Physics references

The hypermultiplet conventions, spectator-dimension factors, beta-function
normalization, finite simple-factor list, and the symplectic global-anomaly
integrality condition follow Sections 2–3 and Tables 1–3 of
[Bhardwaj and Tachikawa, *Classification of 4d N=2 gauge theories*](https://arxiv.org/abs/1309.5160).
The restriction to the conventional Witten anomaly on spin four-manifolds is
consistent with [Wang, Wen, and Witten, *A New SU(2) Anomaly*](https://arxiv.org/abs/1810.00844),
which also discusses the analogous symplectic-group anomaly.
