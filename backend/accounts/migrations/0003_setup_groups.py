from django.db import migrations
from django.core.management import call_command

def run_setup_groups(apps, schema_editor):
    call_command("setup_groups")

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_user_role'),
        ('farms', '0001_initial'),
        ('recommendations', '0001_initial'),
        ('rotation', '0001_initial'),
        ('advisory', '0001_initial'),
        ('feedback', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(run_setup_groups, reverse_code=migrations.RunPython.noop),
    ]
