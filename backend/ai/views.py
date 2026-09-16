import json
import re
import urllib.request
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.views.decorators.http import require_POST
from advisory.models import CropAdvisory
from farms.models import Farm

# Retrieve Gemini API Key
GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", None)
if not GEMINI_API_KEY:
    try:
        from decouple import config
        GEMINI_API_KEY = config("GEMINI_API_KEY", default=None)
    except Exception:
        GEMINI_API_KEY = None

def call_gemini_api(prompt):
    if not GEMINI_API_KEY:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "maxOutputTokens": 800,
            "temperature": 0.3,
        }
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None

GENERIC_STAGE_ADVICE = {
    "Diseases": (
        "Possible causes for yellowing or sickly leaves:\n\n"
        "1. **Nitrogen deficiency:** low soil Nitrogen causes leaves to fade to pale green or yellow, starting from the tips.\n"
        "2. **Waterlogging:** poor drainage suffocates the roots. Dig ridges or drainage channels so water can run off.\n"
        "3. **A virus:** if leaves curl and show a yellow-green mosaic pattern, uproot and burn the infected plants so it doesn't spread.\n\n"
        "**What to do:** check your farm's latest soil log on your dashboard. If Nitrogen is low, apply compost or top-dress with Urea or NPK."
    ),
    "Fertilizer": (
        "General fertilizer advice:\n\n"
        "1. **At planting:** apply NPK 17:17:17 or DAP (about 50kg/acre) to help roots establish well.\n"
        "2. **Top-dressing:** for cereals like maize, apply Nitrogen-rich Urea 5-6 weeks in, once plants are knee-high.\n"
        "3. **Legumes (beans, groundnuts):** these fix their own nitrogen, so focus on Phosphorus-rich fertilizers (TSP/SSP) instead.\n\n"
        "**Note:** always apply fertilizer when the soil is moist, and keep it off the leaves to avoid burning the plant."
    ),
    "Weeding": (
        "Weeding advice:\n\n"
        "1. **When it matters most:** keep fields weed-free for the first 4-8 weeks, while young crops are most affected by competition.\n"
        "2. **How:** hand-weed or hoe shallowly. Avoid digging deep near the roots, especially for tubers like cassava and sweet potato.\n"
        "3. **Best timing:** weed on a sunny morning so pulled weeds dry out and die quickly. Avoid weeding when the crop is wet, since that spreads fungal disease."
    ),
    "Pests": (
        "Pest control advice:\n\n"
        "1. **Check regularly:** walk your fields weekly and look under leaves and around stems for early signs.\n"
        "2. **Caterpillars (like fall armyworm):** hand-pick them if there are only a few. For bigger infestations, spray in the evening.\n"
        "3. **Aphids and whiteflies:** a soapy water spray or neem oil usually works well against these sap-sucking pests."
    ),
}

# Natural phrasings for crops whose dataset key is a squashed compound word
# (e.g. "sweetpotato"), so a farmer typing the normal spaced-out name still
# matches. Checked before the bare crop_name so the more specific phrase wins.
CROP_ALIASES = {
    "pigeon peas": "pigeonpeas", "pigeon pea": "pigeonpeas",
    "sweet potato": "sweetpotato", "sweet potatoes": "sweetpotato",
    "soya bean": "soyabean", "soya beans": "soyabean", "soybean": "soyabean", "soybeans": "soyabean",
    "black gram": "blackgram",
    "garden bean": "gardenbean", "garden beans": "gardenbean",
    "green bean": "gardenbean", "green beans": "gardenbean",
    "kidney bean": "kidneybeans", "kidney beans": "kidneybeans",
    "mung bean": "mungbean", "mung beans": "mungbean", "green gram": "mungbean",
    "musk melon": "muskmelon", "cantaloupe": "muskmelon",
    "sesame seed": "sesameseed", "sesame": "sesameseed", "simsim": "sesameseed",
    "sunflower seed": "sunflowerseed", "sunflower": "sunflowerseed",
    "moth bean": "mothbeans", "moth beans": "mothbeans",
    "bean": "kidneybeans", "beans": "kidneybeans",
}

# Topic words -> the CropAdvisory stage they map to. Checked in order, first
# match wins, so put the more specific/diagnostic words first.
STAGE_KEYWORDS = [
    ("Diseases", ["disease", "diseases", "virus", "fungus", "fungal", "wilt", "wilting", "rot", "rotting",
                  "blight", "sick", "sickly", "unhealthy", "dying", "spots", "pale",
                  "yellow", "yellowing", "leaves", "leaf", "foliage"]),
    ("Pests", ["pest", "pests", "insect", "insects", "caterpillar", "caterpillars",
               "aphid", "aphids", "armyworm", "bug", "bugs"]),
    ("Fertilizer", ["fertilizer", "fertiliser", "manure", "nutrient", "nutrients", "npk", "compost", "top-dress", "topdress"]),
    ("Weeding", ["weed", "weeds", "weeding", "grass"]),
    ("Harvest", ["harvest", "harvesting"]),
    ("Storage", ["storage", "store", "storing", "spoilage", "spoil"]),
    ("Preparation", ["land preparation", "prepare the land", "clear the field", "plough", "plow", "till", "tilling"]),
    ("Planting", ["plant", "planting", "spacing", "sow", "sowing", "seed rate"]),
]

STAGE_LABELS = dict(CropAdvisory.STAGE_CHOICES)


def _word_match(pattern, message):
    return re.search(r"\b" + re.escape(pattern) + r"\b", message) is not None


def _find_crop(message, known_crops):
    candidates = [(alias, canonical) for alias, canonical in CROP_ALIASES.items() if canonical in known_crops]
    candidates += [(crop, crop) for crop in known_crops]
    candidates.sort(key=lambda pair: len(pair[0]), reverse=True)
    for pattern, canonical in candidates:
        if _word_match(pattern, message):
            return canonical
    return None


def _find_stage(message):
    for stage, keywords in STAGE_KEYWORDS:
        for keyword in keywords:
            if _word_match(keyword, message):
                return stage
    return None


def _farm_soil_note(farm):
    """A short, honest note about the farmer's actual latest soil test,
    using the same thresholds as the dashboard's soil alerts, so the chat
    doesn't stay silent about data the app already has for this farm."""
    if not farm:
        return ""
    latest = farm.soil_records.first()
    if not latest:
        return ""

    issues = []
    if latest.nitrogen < 30:
        issues.append(f"Nitrogen is low ({latest.nitrogen} mg/kg)")
    if latest.phosphorus < 20:
        issues.append(f"Phosphorus is low ({latest.phosphorus} mg/kg)")
    if latest.potassium < 30:
        issues.append(f"Potassium is low ({latest.potassium} mg/kg)")
    if latest.ph < 5.0 or latest.ph > 8.0:
        issues.append(f"soil pH is out of range ({latest.ph})")

    if not issues:
        return f"\n\n**Your farm '{farm.farm_name}':** your latest soil test doesn't show any critical issues."
    return f"\n\n**Your farm '{farm.farm_name}':** {'; '.join(issues)}, based on your latest soil test."


def _crop_advisory_reply(crop, stage):
    entries = CropAdvisory.objects.filter(crop_name=crop)
    if not entries.exists():
        return None

    if stage:
        match = entries.filter(stage=stage).first()
        if match:
            return (
                f"**{match.title}**\n\n{match.description}\n\n"
                f"For the complete stage-by-stage guide, open the **Knowledge Base** tab and select {crop.title()}."
            )

    available_stages = [STAGE_LABELS.get(s, s) for s in entries.values_list("stage", flat=True)]
    listed = ", ".join(available_stages)
    return (
        f"I have a growing guide for **{crop.title()}** covering: {listed}.\n\n"
        f"Ask me something more specific, like 'How do I plant {crop.title()}?' or "
        f"'What fertilizer does {crop.title()} need?', or open the **Knowledge Base** tab "
        f"and select {crop.title()} to see everything at once."
    )


def get_keyword_fallback(message, farm=None):
    message = message.lower()
    known_crops = list(CropAdvisory.objects.values_list("crop_name", flat=True).distinct())

    crop = _find_crop(message, known_crops)
    stage = _find_stage(message)

    if crop:
        reply = _crop_advisory_reply(crop, stage)
        if reply:
            if stage in (None, "Fertilizer", "Diseases"):
                reply += _farm_soil_note(farm)
            return reply

    if stage:
        advice = GENERIC_STAGE_ADVICE.get(stage)
        if advice:
            if stage in ("Fertilizer", "Diseases"):
                advice += _farm_soil_note(farm)
            return advice
        return (
            f"I can help with {STAGE_LABELS.get(stage, stage).lower()}, but I'll need to know which crop "
            f"you mean, since it's different for each one. Which crop are you asking about?"
        )

    if _word_match("soil", message) or _word_match("farm", message):
        note = _farm_soil_note(farm)
        if note:
            return "Here's what I can tell you about your soil:" + note + \
                "\n\nAsk me about a specific crop or topic (like fertilizer, weeding, or pests) for more detailed advice."

    return (
        "Thanks for reaching out! I can help with any of the crops grown here, for example:\n"
        "- Crop guidelines (e.g., 'How do I plant maize?' or 'Beans spacing')\n"
        "- Leaf issues ('My bean leaves are turning yellow')\n"
        "- Weed management ('When should I weed my fields?')\n"
        "- Pest control ('How do I deal with caterpillars?')\n\n"
        "You can also check the **Knowledge Base** tab for the complete stage-by-stage guide for any of our 38 crops."
    )

@login_required
@require_POST
def clear_chat(request):
    request.session["chat_history"] = []
    return redirect("ai:chat")


@login_required
def chat(request):
    chat_history = request.session.get("chat_history", [])
    farms = Farm.objects.filter(user=request.user)

    selected_farm = None

    if request.method == "POST":
        user_message = request.POST.get("message", "").strip()
        selected_farm_id = request.POST.get("farm_id")

        if user_message:
            context = ""
            farm = None
            if selected_farm_id:
                try:
                    farm = Farm.objects.get(id=selected_farm_id, user=request.user)
                    latest_soil = farm.soil_records.first()
                    context = f"The farmer is asking about their farm '{farm.farm_name}' located in {farm.district}, Uganda. Soil type: {farm.soil_type}."
                    if latest_soil:
                        context += (
                            f" The latest soil analysis: Nitrogen: {latest_soil.nitrogen} mg/kg, "
                            f"Phosphorus: {latest_soil.phosphorus} mg/kg, Potassium: {latest_soil.potassium} mg/kg, "
                            f"pH: {latest_soil.ph}, Temperature: {latest_soil.temperature}°C, Rainfall: {latest_soil.rainfall} mm."
                        )
                except Farm.DoesNotExist:
                    pass

            # Grounding prompt structure
            prompt = (
                "You are the CropAI Assistant, a friendly and knowledgeable crop advisor "
                "for smallholder farmers in Uganda. Give short, clear, practical advice in plain language, "
                "avoiding technical jargon a farmer without formal agricultural training wouldn't know. "
                "Only give planting distances or fertilizer rates that reflect widely accepted, publicly known farming practice, "
                "and don't invent numbers you're not confident about. "
                "If the question involves specific soil values, refer back to the context provided. "
                "Format your response in Markdown.\n\n"
            )
            if context:
                prompt += f"Context:\n{context}\n\n"
            prompt += f"Farmer Question:\n{user_message}"

            bot_response = call_gemini_api(prompt)

            if not bot_response:
                bot_response = get_keyword_fallback(user_message, farm=farm)

            chat_history.append({"sender": "user", "text": user_message})
            chat_history.append({"sender": "bot", "text": bot_response})
            request.session["chat_history"] = chat_history

            return redirect("ai:chat")

    return render(request, "ai/chat.html", {
        "chat_history": chat_history,
        "farms": farms,
    })
