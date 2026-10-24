"""python -m ml.train. Stdlib only; deterministic synthetic dataset and training.

Each row represents an independent fictional company. Targets are noisy sampled
outcomes from a declared synthetic mechanism, not the rule-based score labels.
These metrics measure reproduction of that mechanism, not real credit quality.
"""

import hashlib
import json
import math
import random
from pathlib import Path
from statistics import mean, pstdev

from ml.inference import features

SEED = 20261023
TARGET = "Учебная вероятность просрочки >30 дней в следующие 12 месяцев"


def sigmoid(value):
    return 1 / (1 + math.exp(-max(-40, min(40, value))))


def dataset():
    rng = random.Random(SEED)
    rows = []
    for _ in range(6000):
        margin = rng.uniform(-0.10, 0.55)
        dscr = rng.uniform(0.15, 4.5)
        age = rng.randrange(1, 121)
        overdue = rng.choices(
            [0, rng.randrange(1, 31), rng.randrange(31, 121)], [65, 23, 12]
        )[0]
        # Hidden macro/liquidity shock is deliberately unavailable to the model.
        shock = rng.gauss(0, 0.8)
        p = sigmoid(
            0.5 - 1.1 * dscr - 2.5 * margin - 0.009 * age + 0.027 * overdue + shock
        )
        rows.append((features(dscr, margin, age, overdue), int(rng.random() < p)))
    rng.shuffle(rows)
    return rows


def metrics(rows, probabilities, threshold=0.5):
    n = len(rows)
    labels = [y for _, y in rows]
    positives = sum(labels)
    # Pairwise AUC with ties, implemented through grouped ranks.
    order = sorted(zip(probabilities, labels))
    negatives_before, concordant, i = 0, 0.0, 0
    while i < n:
        j = i
        while j < n and order[j][0] == order[i][0]:
            j += 1
        pos = sum(y for _, y in order[i:j])
        neg = j - i - pos
        concordant += pos * (negatives_before + 0.5 * neg)
        negatives_before += neg
        i = j
    auc = concordant / (positives * (n - positives))
    tp, fp, ap, i = 0, 0, 0.0, 0
    order.reverse()
    while i < n:
        j = i
        while j < n and order[j][0] == order[i][0]:
            j += 1
        pos = sum(y for _, y in order[i:j])
        tp += pos
        fp += j - i - pos
        ap += (pos / positives) * tp / (tp + fp)
        i = j
    bins = []
    for b in range(10):
        items = [
            (p, y) for p, y in zip(probabilities, labels) if b / 10 <= p < (b + 1) / 10
        ]
        if items:
            bins.append(
                dict(
                    bin=b,
                    count=len(items),
                    predicted=round(mean(p for p, _ in items), 5),
                    observed=round(mean(y for _, y in items), 5),
                )
            )
    return dict(
        n=n,
        positive_rate=round(positives / n, 5),
        roc_auc=round(auc, 5),
        average_precision=round(ap, 5),
        brier=round(mean((p - y) ** 2 for p, y in zip(probabilities, labels)), 5),
        confusion_matrix=dict(
            tp=sum(p >= threshold and y == 1 for p, y in zip(probabilities, labels)),
            fp=sum(p >= threshold and y == 0 for p, y in zip(probabilities, labels)),
            tn=sum(p < threshold and y == 0 for p, y in zip(probabilities, labels)),
            fn=sum(p < threshold and y == 1 for p, y in zip(probabilities, labels)),
        ),
        calibration_bins=bins,
    )


def train():
    rows = dataset()
    train_rows, validation, test = rows[:4200], rows[4200:5100], rows[5100:]
    means = [mean(x[i] for x, _ in train_rows) for i in range(4)]
    scales = [pstdev(x[i] for x, _ in train_rows) for i in range(4)]

    def normalize(x):
        return [(v - m) / s for v, m, s in zip(x, means, scales)]

    data = [(normalize(x), y) for x, y in train_rows]
    weights, bias = [0.0] * 4, 0.0
    for _ in range(220):
        gradient, gb = [0.0] * 4, 0.0
        for x, y in data:
            residual = sigmoid(bias + sum(w * v for w, v in zip(weights, x))) - y
            gb += residual
            for i in range(4):
                gradient[i] += residual * x[i]
        bias -= 0.15 * gb / len(data)
        weights = [
            w - 0.15 * (g / len(data) + 0.002 * w) for w, g in zip(weights, gradient)
        ]

    def predictions(data):
        return [
            sigmoid(bias + sum(w * v for w, v in zip(weights, normalize(x))))
            for x, _ in data
        ]

    val_probs = predictions(validation)

    # Select threshold only on validation; model coefficients never see holdout.
    def balanced_accuracy(threshold):
        pos = sum(y for _, y in validation)
        neg = len(validation) - pos
        return (
            sum(p >= threshold and y == 1 for p, (_, y) in zip(val_probs, validation))
            / pos
            + sum(p < threshold and y == 0 for p, (_, y) in zip(val_probs, validation))
            / neg
        ) / 2

    threshold = max([i / 100 for i in range(5, 76)], key=balanced_accuracy)
    fingerprint = hashlib.sha256(
        json.dumps(rows, separators=(",", ":")).encode()
    ).hexdigest()
    model = dict(
        model_version="synthetic_logit_v1",
        target=TARGET,
        seed=SEED,
        means=means,
        scales=scales,
        coefficients=weights,
        intercept=bias,
        dataset_sha256=fingerprint,
    )
    report = dict(
        seed=SEED,
        train_n=4200,
        validation_n=900,
        test_n=900,
        threshold=threshold,
        validation=metrics(validation, val_probs, threshold),
        test=metrics(test, predictions(test), threshold),
        constant_baseline=metrics(
            test, [mean(y for _, y in train_rows)] * len(test), threshold
        ),
        dataset_sha256=fingerprint,
        limitation="Only synthetic data; cannot establish real-world accuracy or default calibration.",
    )
    directory = Path(__file__).parent
    (directory / "model.json").write_text(
        json.dumps(model, ensure_ascii=False, indent=2) + "\n"
    )
    (directory / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                key: report["test"][key]
                for key in ("n", "roc_auc", "average_precision", "brier")
            }
        )
    )


if __name__ == "__main__":
    train()
