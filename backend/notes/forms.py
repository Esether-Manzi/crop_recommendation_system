from django import forms

from farms.models import Farm
from .models import Note


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["title", "farm", "content"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g., Noticed early blight on the tomatoes"}),
            "farm": forms.Select(attrs={"class": "form-select"}),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 5, "placeholder": "Write your notes here..."}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["farm"].queryset = Farm.objects.filter(user=user) if user else Farm.objects.none()
        self.fields["farm"].required = False
        self.fields["farm"].empty_label = "No specific farm"
