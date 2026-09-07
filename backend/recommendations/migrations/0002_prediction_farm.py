import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("farms", "0001_initial"),
        ("recommendations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="prediction",
            name="farm",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="predictions",
                to="farms.farm",
            ),
        ),
    ]
