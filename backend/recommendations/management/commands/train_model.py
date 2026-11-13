from pathlib import Path

from django.core.management.base import BaseCommand

from ml.training import MODEL_DIR, train


class Command(BaseCommand):
    help = (
        "Runs the full ML pipeline (load, validate, harmonise rainfall, split, compare models, "
        "tune, evaluate) and saves the model with a model card. Restart the server afterwards "
        "so the new model is loaded."
    )

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", default=str(MODEL_DIR),
                            help="Where to save artifacts. Defaults to the live model directory.")
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--test-size", type=float, default=0.2)
        parser.add_argument("--folds", type=int, default=10)
        parser.add_argument("--no-tune", action="store_true", help="Skip grid search (much faster).")
        parser.add_argument("--deploy", default="best",
                            help='"best" (highest CV macro F1, the default) or a model name to override.')
        parser.add_argument("--models", default="",
                            help='Comma-separated subset to compare, e.g. "XGBoost,Random Forest,Naive Bayes".')

    def handle(self, *args, **options):
        card = train(
            output_dir=Path(options["output_dir"]),
            seed=options["seed"],
            test_size=options["test_size"],
            folds=options["folds"],
            tune=not options["no_tune"],
            deploy=options["deploy"],
            models=[m.strip() for m in options["models"].split(",") if m.strip()],
            log=self.stdout.write,
        )
        metrics = card["test_metrics"]
        self.stdout.write(self.style.SUCCESS(
            f"Model {card['version']} ({card['algorithm']}): test accuracy {metrics['accuracy']:.4f}, "
            f"macro F1 {metrics['f1_macro']:.4f}"
        ))
