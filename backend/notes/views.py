from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import NoteForm
from .models import Note


@login_required
def notes_list(request):
    notes = Note.objects.filter(user=request.user)

    if request.method == "POST":
        form = NoteForm(request.POST, user=request.user)
        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user
            note.save()
            messages.success(request, f"Note '{note.title}' saved!")
            return redirect("notes:list")
    else:
        form = NoteForm(user=request.user)

    return render(request, "notes/notes_list.html", {"notes": notes, "form": form})


@login_required
def note_edit(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)

    if request.method == "POST":
        form = NoteForm(request.POST, instance=note, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Note updated!")
            return redirect("notes:list")
    else:
        form = NoteForm(instance=note, user=request.user)

    return render(request, "notes/note_edit.html", {"form": form, "note": note})


@login_required
@require_POST
def note_delete(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)
    note.delete()
    messages.success(request, "Note deleted.")
    return redirect("notes:list")
