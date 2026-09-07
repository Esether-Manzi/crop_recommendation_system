from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

class Command(BaseCommand):
    help = "Creates Farmer, Extension Officer, and System Admin groups with use-case authorizations."

    def handle(self, *args, **options):
        # Create groups if they do not exist
        farmer_group, _ = Group.objects.get_or_create(name="Farmer")
        officer_group, _ = Group.objects.get_or_create(name="Extension Officer")
        admin_group, _ = Group.objects.get_or_create(name="System Admin")

        # Helper to retrieve permission objects
        def get_permission_objects(app_label, model_name, actions):
            perms = []
            for action in actions:
                codename = f"{action}_{model_name}"
                try:
                    perm = Permission.objects.get(codename=codename, content_type__app_label=app_label)
                    perms.append(perm)
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"Permission '{codename}' in app '{app_label}' not found."))
            return perms

        # 1. Assign Farmer Permissions
        farmer_permissions = (
            get_permission_objects("farms", "farm", ["add", "change", "delete", "view"]) +
            get_permission_objects("farms", "soilrecord", ["add", "change", "delete", "view"]) +
            get_permission_objects("recommendations", "prediction", ["add", "change", "delete", "view"]) +
            get_permission_objects("rotation", "rotationplan", ["add", "change", "delete", "view"]) +
            get_permission_objects("rotation", "rotationstep", ["add", "change", "delete", "view"]) +
            get_permission_objects("advisory", "cropadvisory", ["view"]) +
            get_permission_objects("advisory", "seasontracker", ["add", "change", "delete", "view"]) +
            get_permission_objects("feedback", "harvestfeedback", ["add", "change", "delete", "view"])
        )
        farmer_group.permissions.set(farmer_permissions)
        self.stdout.write(self.style.SUCCESS("Assigned permissions to 'Farmer' group."))

        # 2. Assign Extension Officer Permissions
        officer_permissions = (
            get_permission_objects("farms", "farm", ["view"]) +
            get_permission_objects("farms", "soilrecord", ["view"]) +
            get_permission_objects("recommendations", "prediction", ["view"]) +
            get_permission_objects("rotation", "rotationplan", ["view"]) +
            get_permission_objects("rotation", "rotationstep", ["view"]) +
            get_permission_objects("advisory", "cropadvisory", ["view"]) +
            get_permission_objects("advisory", "seasontracker", ["view"]) +
            get_permission_objects("feedback", "harvestfeedback", ["view"]) +
            get_permission_objects("accounts", "user", ["view"])
        )
        officer_group.permissions.set(officer_permissions)
        self.stdout.write(self.style.SUCCESS("Assigned permissions to 'Extension Officer' group."))

        # 3. Assign System Admin Permissions
        admin_permissions = (
            get_permission_objects("farms", "farm", ["add", "change", "delete", "view"]) +
            get_permission_objects("farms", "soilrecord", ["add", "change", "delete", "view"]) +
            get_permission_objects("recommendations", "prediction", ["add", "change", "delete", "view"]) +
            get_permission_objects("rotation", "rotationplan", ["add", "change", "delete", "view"]) +
            get_permission_objects("rotation", "rotationstep", ["add", "change", "delete", "view"]) +
            get_permission_objects("advisory", "cropadvisory", ["add", "change", "delete", "view"]) +
            get_permission_objects("advisory", "seasontracker", ["add", "change", "delete", "view"]) +
            get_permission_objects("feedback", "harvestfeedback", ["add", "change", "delete", "view"]) +
            get_permission_objects("accounts", "user", ["add", "change", "delete", "view"])
        )
        admin_group.permissions.set(admin_permissions)
        self.stdout.write(self.style.SUCCESS("Assigned permissions to 'System Admin' group."))
