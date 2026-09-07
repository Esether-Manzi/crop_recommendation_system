import json
import urllib.request
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.views.decorators.http import require_POST
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

def get_keyword_fallback(message):
    message = message.lower()
    if "yellow" in message or "leaves" in message or "leaf" in message:
        return (
            "Possible causes for yellowing leaves:\n\n"
            "1. **Nitrogen Deficiency:** Low soil Nitrogen causes leaves to fade to pale green/yellow starting from the tips.\n"
            "2. **Waterlogging:** Poor soil drainage suffocates root breathing. Ensure ridges are dug to let water run off.\n"
            "3. **Bean Mosaic Virus:** If leaves curl and show yellow-green mosaic patterns. Immediately rogue (uproot) and burn infected plants.\n\n"
            "**Recommended Action:** Inspect your farm's latest soil log on your dashboard. If Nitrogen is low, apply organic compost or top-dress with Urea/NPK."
        )
    elif "fertilizer" in message or "manure" in message or "nutrients" in message or "npk" in message:
        return (
            "General Nutrient and Fertilizer Advice:\n\n"
            "1. **Basal Application:** Apply NPK 17:17:17 or DAP at planting (approx 50kg/acre) to establish healthy root structures.\n"
            "2. **Top-Dressing:** For cereal crops like Maize, apply Nitrogen-rich Urea at 5-6 weeks when plants are knee-high.\n"
            "3. **Legumes (Beans/Groundnuts):** Beans fix their own nitrogen. Focus on Phosphorus-rich fertilizers (TSP/SSP) instead of heavy nitrogen feeding.\n\n"
            "**Note:** Always apply fertilizer when the soil is moist. Avoid placement directly on crop leaves to prevent burning."
        )
    elif "weed" in message or "weeding" in message or "grass" in message:
        return (
            "Weeding Best Practices:\n\n"
            "1. **Critical Period:** Maintain weed-free conditions during the first 4-8 weeks when young crops are highly competitive.\n"
            "2. **Method:** Hand-weed or hoe shallowly. Avoid deep digging near surface roots, especially for tubers like Cassava and Sweet Potatoes.\n"
            "3. **Timing:** Weed in the morning of a sunny day so weeds wither quickly. Never weed when the crop foliage is wet, as this spreads fungal pathogens."
        )
    elif "pest" in message or "insect" in message or "caterpillar" in message or "aphids" in message:
        return (
            "Pest and Insect Management:\n\n"
            "1. **Scouting:** Walk through your fields weekly in a diagonal pattern. Inspect the leaf undersides and stem collars.\n"
            "2. **Caterpillars (e.g. Fall Armyworm):** Hand-pick if infestation is small. Otherwise, apply Emamectin benzoate or Lufenuron in the late evenings.\n"
            "3. **Aphids/Whiteflies:** Spray with organic soapy water solutions or Neem oil extract to suppress sap-sucking insects that transmit viral diseases."
        )
    elif "maize" in message:
        return (
            "Quick Maize Guidelines:\n\n"
            "- **Spacing:** 75cm x 25cm, 1 seed per hole.\n"
            "- **Fertilizer:** DAP at planting, Urea at knee-high (week 5-6).\n"
            "- **Weeding:** Weed at week 3 and week 6.\n"
            "- **Harvest:** Dry ears in fields until moisture drops below 20%, then dry on tarps."
        )
    elif "bean" in message or "beans" in message:
        return (
            "Quick Beans Guidelines:\n\n"
            "- **Spacing:** 50cm x 10cm, plant 3-4cm deep.\n"
            "- **Fertilizer:** Apply Phosphorus basal fertilizers at planting.\n"
            "- **Weeding:** First weed at week 2-3. Do not weed during flowering.\n"
            "- **Harvest:** Uproot entire plants in the morning when pods turn yellow-brown."
        )
    elif "cassava" in message:
        return (
            "Quick Cassava Guidelines:\n\n"
            "- **Spacing:** 1m x 1m. Plant healthy CMD-tolerant stem cuttings at 45 degrees.\n"
            "- **Weeding:** Regularly weed for 3-4 months until crop canopy shading takes over.\n"
            "- **Harvest:** Harvest at 9-12 months. Process into chips or flour within 48 hours to avoid spoilage."
        )
    else:
        return (
            "Thank you for reaching out! To give you the most accurate response, please ask about:\n"
            "- Crop guidelines (e.g., 'How do I plant Maize?' or 'Beans spacing')\n"
            "- Leaf issues ('My bean leaves are turning yellow')\n"
            "- Weed management ('When should I weed my fields?')\n"
            "- Pest controls ('How do I kill caterpillars?')\n\n"
            "You can also check the **Advisory** tab for complete stage-by-stage manuals."
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
                "You are Antigravity Agronomist, a highly knowledgeable and supportive AI crop advisor "
                "for local smallholder farmers in Uganda. Provide concise, clear, and action-oriented agronomic advice. "
                "Do not invent planting distances or fertilizer rates that are not present in standard FAO/NARO manuals. "
                "If the query involves specific soil parameters, refer back to the context provided. "
                "Format your response in Markdown.\n\n"
            )
            if context:
                prompt += f"Context:\n{context}\n\n"
            prompt += f"Farmer Question:\n{user_message}"

            bot_response = call_gemini_api(prompt)

            if not bot_response:
                bot_response = get_keyword_fallback(user_message)

            chat_history.append({"sender": "user", "text": user_message})
            chat_history.append({"sender": "bot", "text": bot_response})
            request.session["chat_history"] = chat_history

            return redirect("ai:chat")

    return render(request, "ai/chat.html", {
        "chat_history": chat_history,
        "farms": farms,
    })
