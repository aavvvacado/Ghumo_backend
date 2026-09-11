import json
import logging
import re
from typing import Dict, Any, List, Optional
from app.services.ai_service import ai_service
from app.services.search_service import search_service
from app.services.place_image_resolver import place_image_resolver

logger = logging.getLogger(__name__)

class ItineraryService:
    async def parse_user_intent(self, prompt: str, location: Optional[str] = None, 
                                  time_available: Optional[str] = None, 
                                  interests: Optional[List[str]] = None, 
                                  budget: Optional[str] = None) -> Dict[str, Any]:
        """
        Parses raw conversational text and fills in any missing constraints.
        Produces standardized destination, duration, budget, mode, and interests.
        """
        def _clean_dummy(val: Optional[str]) -> Optional[str]:
            if not val or not isinstance(val, str):
                return None
            cleaned = val.strip()
            if cleaned.lower() in ["string", "null", "undefined", "none", "n/a"]:
                return None
            return cleaned

        location = _clean_dummy(location)
        time_available = _clean_dummy(time_available)
        budget = _clean_dummy(budget)
        user_input_raw = (prompt or "").strip()
        
        # If user gave explicit structured fields and no free-form prompt
        if not user_input_raw and location:
            loc = location.strip()
            time_str = (time_available or "2 days").strip()
            mode = "time_wise" if any(unit in time_str.lower() for unit in ["hour", "hr", "morning", "afternoon", "evening", "half day"]) else "day_wise"
            return {
                "destination": loc,
                "duration": time_str,
                "mode": mode,
                "budget": (budget or "moderate").strip(),
                "interests": interests or ["sightseeing", "local food", "culture"],
                "stay_preference": "central and accessible neighborhood"
            }

        extraction_prompt = (
            "You are an expert travel intent parser. Extract the travel details from the user's request.\n"
            f"User Input: \"{user_input_raw}\"\n"
            f"Provided location field (if any): \"{location or ''}\"\n"
            f"Provided duration field (if any): \"{time_available or ''}\"\n"
            f"Provided budget field (if any): \"{budget or ''}\"\n"
            f"Provided interests (if any): \"{', '.join(interests or [])}\"\n\n"
            "Return a clean JSON object with EXACTLY these keys:\n"
            "- destination: (string, clean place or city name, e.g., 'Goa', 'Jaipur', 'Chandni Chowk, Delhi')\n"
            "- duration: (string, e.g. '3 days', '2 days / 1 night', '6 hours', '1 day')\n"
            "- mode: ('day_wise' if 1 or more days, 'time_wise' if less than 1 day or hourly/morning/evening)\n"
            "- budget: (string, e.g. '10000 INR', 'budget / ₹2000 per day', 'moderate', 'luxury')\n"
            "- interests: (list of strings, e.g. ['beaches', 'nightlife', 'seafood'])\n"
            "- stay_preference: (string, recommended stay zone or type based on budget and vibe)\n\n"
            "If any field is missing or unstated by the user, intelligently infer practical and vibrant defaults.\n"
            "Output JSON ONLY without markdown wrapping or conversational commentary."
        )

        system_instruction = "You are a travel NLP parser. Always output valid raw JSON."
        ai_raw = await ai_service.generate_content(extraction_prompt, system_instruction)

        try:
            cleaned = re.sub(r"^```json\s*", "", ai_raw.strip(), flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned.strip())
            parsed = json.loads(cleaned)
            
            destination = parsed.get("destination") or location or "Incredible India"
            duration = parsed.get("duration") or time_available or "2 days"
            mode = parsed.get("mode") or ("time_wise" if any(u in duration.lower() for u in ["hour", "hr", "evening", "morning"]) else "day_wise")
            parsed_budget = parsed.get("budget") or budget or "moderate"
            parsed_interests = parsed.get("interests") or (interests if interests else ["sightseeing", "local food"])
            stay_pref = parsed.get("stay_preference") or "central and vibrant area"

            return {
                "destination": destination,
                "duration": duration,
                "mode": mode,
                "budget": parsed_budget,
                "interests": parsed_interests,
                "stay_preference": stay_pref
            }
        except Exception as e:
            logger.warning(f"Failed to parse travel intent JSON: {e}. Falling back to default extraction.")
            # Simple fallback
            dest = location or user_input_raw.split("for")[0].replace("visiting", "").replace("iam", "").strip() or "Goa"
            return {
                "destination": dest,
                "duration": time_available or "2 days",
                "mode": "day_wise",
                "budget": budget or "moderate",
                "interests": interests or ["sightseeing", "culture"],
                "stay_preference": "central area"
            }

    def _generate_markdown_table(self, plan_data: Dict[str, Any]) -> str:
        """
        Converts the structured plan data into a clean, standardized Markdown table.
        """
        mode = plan_data.get("mode", "day_wise")
        lines = []
        lines.append("| Timing / Slot | Place / Landmark | Duration | Purpose & Highlights | Estimated Cost |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")

        if mode == "day_wise" and plan_data.get("days"):
            for day_chunk in plan_data["days"]:
                day_num = day_chunk.get("day", 1)
                day_title = day_chunk.get("title", f"Day {day_num}")
                stay = day_chunk.get("stay_recommendation", "")
                cost = day_chunk.get("estimated_day_cost", "")
                header_info = f"**DAY {day_num}: {day_title}**"
                if cost: header_info += f" (Est: {cost})"
                if stay: header_info += f" | Stay: {stay}"
                lines.append(f"| {header_info} | | | | |")
                
                for act in day_chunk.get("activities", []):
                    slot = act.get("time_slot", "Daytime")
                    place = act.get("place", "Featured Attraction")
                    dur = act.get("duration", "2 hrs")
                    purpose = act.get("purpose", "Explore & Enjoy")
                    act_cost = act.get("cost_estimate", "Free")
                    lines.append(f"| {slot} | **{place}** | {dur} | {purpose} | {act_cost} |")
        elif plan_data.get("time_slots"):
            for slot_chunk in plan_data["time_slots"]:
                slot_name = slot_chunk.get("slot", "Time Slot")
                t_range = slot_chunk.get("time_range", "")
                slot_label = f"**{slot_name}**"
                if t_range: slot_label += f" ({t_range})"
                lines.append(f"| {slot_label} | | | | |")

                for act in slot_chunk.get("activities", []):
                    slot = act.get("time_slot", slot_name)
                    place = act.get("place", "Featured Attraction")
                    dur = act.get("duration", "1.5 hrs")
                    purpose = act.get("purpose", "Highlights & Sightseeing")
                    act_cost = act.get("cost_estimate", "Free")
                    lines.append(f"| {slot} | **{place}** | {dur} | {purpose} | {act_cost} |")

        return "\n".join(lines)

    async def generate_itinerary(self, location: Optional[str] = None, 
                                 time_available: Optional[str] = None, 
                                 interests: Optional[list] = None, 
                                 budget: Optional[str] = None,
                                 prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates a rich, chunked (day-wise or time-wise), and standardized travel itinerary
        supporting free-form text or structured input with real image resolution.
        """
        # 1. Parse intent & extract structured constraints
        intent = await self.parse_user_intent(
            prompt=prompt,
            location=location,
            time_available=time_available,
            interests=interests,
            budget=budget
        )
        dest = intent["destination"]
        duration = intent["duration"]
        mode = intent["mode"]
        plan_budget = intent["budget"]
        interests_list = intent["interests"]
        stay_pref = intent["stay_preference"]

        # 2. Query verified places from local database and OpenStreetMap
        data = await search_service.search_all(dest)

        # If dest has multiple components (e.g. "Muradnagar, Ghaziabad"), pull and merge POIs
        attraction_items = list(data.get("attractions", []))
        food_items = list(data.get("food", [])) or list(data.get("restaurants", []))
        market_items = list(data.get("markets", []))
        gem_items = list(data.get("hidden_gems", []))
        transit_items = [p for p in data.get("places", []) if p.get("type") in ["transit_hub", "station"]]

        # Check sub-parts if primary search returned few results
        parts = [p.strip() for p in re.split(r'[,/]| and ', dest) if len(p.strip()) >= 3]
        if len(parts) > 1:
            for sub_part in parts:
                sub_data = await search_service.search_all(sub_part)
                for a in sub_data.get("attractions", []):
                    if a.get("name") not in [x.get("name") for x in attraction_items]:
                        attraction_items.append(a)
                for f in sub_data.get("food", []):
                    if f.get("name") not in [x.get("name") for x in food_items]:
                        food_items.append(f)
                for g in sub_data.get("hidden_gems", []):
                    if g.get("name") not in [x.get("name") for x in gem_items]:
                        gem_items.append(g)
                for m in sub_data.get("markets", []):
                    if m.get("name") not in [x.get("name") for x in market_items]:
                        market_items.append(m)

        has_local_data = len(attraction_items) > 0 or len(food_items) > 0 or len(gem_items) > 0 or len(market_items) > 0

        def _describe_spot(p: dict) -> str:
            name = p.get("name", "")
            p_type = p.get("type", "spot")
            desc = p.get("description", "")
            if desc:
                return f"'{name}' ({p_type}): {desc}"
            return f"'{name}' ({p_type})"

        # 3. Construct structured AI prompt with rich local intelligence
        prompt_instructions = (
            f"You are the world's best local travel curator. Create an extraordinary, highly specific, hyper-authentic travel plan for {dest}.\n"
            f"Target Duration: {duration}\n"
            f"Itinerary Segregation Mode: '{mode}' ('day_wise' for multi-day trips with Day 1, Day 2; 'time_wise' for short same-day trips with Morning, Afternoon, Evening)\n"
            f"Budget: {plan_budget}\n"
            f"Interests & Vibe: {', '.join(interests_list)}\n"
            f"Stay Preference: {stay_pref}\n\n"
            f"STRICT INSTRUCTIONS:\n"
            f"1. NEVER invent vague, generic names like 'Local Temples', 'NH-58 Area', 'Local Eatery', 'Heritage Center', or 'City Market'.\n"
            f"2. You MUST use the EXACT real places, student hangouts, cafes, dhabas, ghats, and landmarks provided below.\n"
            f"3. In each activity's 'notes' and 'purpose', weave in the authentic insider details provided (e.g., student discounts, exact food specialties, pillar numbers, temple timings, Namo Bharat transit links).\n\n"
        )

        if has_local_data:
            prompt_instructions += "VERIFIED LOCAL LANDMARKS & SPOTS (YOU MUST INTEGRATE THESE):\n"
            if attraction_items:
                prompt_instructions += "- Key Attractions & Culture:\n  * " + "\n  * ".join([_describe_spot(a) for a in attraction_items[:12]]) + "\n"
            if food_items:
                prompt_instructions += "- Authentic Local Food, Cafes & Dhabas:\n  * " + "\n  * ".join([_describe_spot(f) for f in food_items[:14]]) + "\n"
            if gem_items:
                prompt_instructions += "- Student Secrets & Hidden Gems:\n  * " + "\n  * ".join([_describe_spot(g) for g in gem_items[:10]]) + "\n"
            if market_items:
                prompt_instructions += "- Local Markets & Bazaars:\n  * " + "\n  * ".join([_describe_spot(m) for m in market_items[:8]]) + "\n"
            if transit_items:
                prompt_instructions += "- Transit Hubs (Namo Bharat RRTS / Rail):\n  * " + "\n  * ".join([_describe_spot(t) for t in transit_items[:4]]) + "\n\n"
        else:
            prompt_instructions += (
                "Verified local database places are sparse for this exact location. Use your expert real-world knowledge "
                "to recommend genuine, highly praised, accurate landmarks, authentic eateries, and hidden gems. "
                "Never invent fictitious names.\n\n"
            )

        json_format_template = """
Return ONLY a valid JSON object matching this EXACT schema:
{
  "summary": "Captivating 2-3 sentence overview of this curated trip",
  "destination": "Location Name",
  "total_duration": "Duration (e.g. 3 Days / 2 Nights or 6 Hours)",
  "estimated_total_budget": "Estimated total cost (e.g. ₹9,500)",
  "stay_area": "Recommended neighborhood/area for stay and why",
  "budget_breakdown": {
    "stay": "Estimated accommodation expense",
    "food": "Estimated dining & street food expense",
    "activities": "Entry tickets & experience expenses",
    "transport": "Local cabs, metro, autos expense"
  },
  "days": [
    {
      "day": 1,
      "title": "Day Theme/Highlight",
      "stay_recommendation": "Neighborhood or hotel recommendation",
      "estimated_day_cost": "Estimated cost for this day",
      "activities": [
        {
          "time_slot": "09:00 AM - 11:30 AM",
          "place": "Real Landmark Name",
          "duration": "2.5 hours",
          "purpose": "Why visit, vibe, what to see/photograph",
          "cost_estimate": "Entry fee or ₹0 if free",
          "notes": "Insider tip (best viewpoint, avoiding crowds, local snack)"
        }
      ]
    }
  ],
  "time_slots": [
    {
      "slot": "Morning",
      "time_range": "09:00 AM - 12:30 PM",
      "activities": [
        {
          "time_slot": "09:00 AM - 10:30 AM",
          "place": "Real Landmark Name",
          "duration": "1.5 hours",
          "purpose": "Activity highlight and purpose",
          "cost_estimate": "Free",
          "notes": "Practical tip"
        }
      ]
    }
  ]
}
Note: If mode is 'day_wise', provide the 'days' array and set 'time_slots' to null. If mode is 'time_wise', provide the 'time_slots' array and set 'days' to null.
"""
        full_generation_prompt = prompt_instructions + json_format_template
        system_prompt = "You are a master travel curator. Always produce clean, valid, detailed JSON travel itineraries."

        ai_response_text = await ai_service.generate_content(full_generation_prompt, system_prompt)

        # 4. Parse JSON plan data
        plan_dict: Dict[str, Any] = {}
        try:
            clean_json = re.sub(r"^```json\s*", "", ai_response_text.strip(), flags=re.IGNORECASE)
            clean_json = re.sub(r"\s*```$", "", clean_json.strip())
            plan_dict = json.loads(clean_json)
        except Exception as e:
            logger.warning(f"Could not parse structured JSON itinerary: {e}. Generating structured fallback.")
            # Graceful fallback structure
            plan_dict = {
                "summary": f"A delightful {duration} journey discovering the finest highlights of {dest}.",
                "destination": dest,
                "total_duration": duration,
                "estimated_total_budget": plan_budget,
                "stay_area": stay_pref,
                "budget_breakdown": {
                    "stay": "40% of budget",
                    "food": "30% of budget",
                    "activities": "15% of budget",
                    "transport": "15% of budget"
                },
                "days": [
                    {
                        "day": 1,
                        "title": f"Explore {dest} Highlights",
                        "stay_recommendation": stay_pref,
                        "estimated_day_cost": plan_budget,
                        "activities": [
                            {
                                "time_slot": "Morning",
                                "place": attractions[0] if attractions else f"{dest} Heritage Center",
                                "duration": "2.5 hours",
                                "purpose": "Iconic sightseeing and architectural photography",
                                "cost_estimate": "Free / Nominal",
                                "notes": "Start early to enjoy the morning light"
                            },
                            {
                                "time_slot": "Afternoon",
                                "place": restaurants[0] if restaurants else f"Famous Local Eatery in {dest}",
                                "duration": "1.5 hours",
                                "purpose": "Authentic regional culinary experience",
                                "cost_estimate": "Moderate",
                                "notes": "Ask for chef specials"
                            }
                        ]
                    }
                ]
            }

        plan_dict["mode"] = mode
        if not plan_dict.get("destination"):
            plan_dict["destination"] = dest

        # 5. Extract all unique place names across the plan for Image Resolution
        places_to_resolve = []
        if mode == "day_wise" and plan_dict.get("days"):
            for day in plan_dict["days"]:
                for act in day.get("activities", []):
                    p_name = act.get("place")
                    if p_name and p_name not in [p["name"] for p in places_to_resolve]:
                        places_to_resolve.append({"name": p_name, "city": dest})
        elif plan_dict.get("time_slots"):
            for slot in plan_dict["time_slots"]:
                for act in slot.get("activities", []):
                    p_name = act.get("place")
                    if p_name and p_name not in [p["name"] for p in places_to_resolve]:
                        places_to_resolve.append({"name": p_name, "city": dest})

        # Concurrent image resolution
        if places_to_resolve:
            try:
                await place_image_resolver.resolve_places_batch(places_to_resolve, city=dest, timeout=2.0)
                # Map resolved images back to activities
                image_map = {p["name"]: p.get("image") for p in places_to_resolve if p.get("image")}
                
                if mode == "day_wise" and plan_dict.get("days"):
                    for day in plan_dict["days"]:
                        for act in day.get("activities", []):
                            if act.get("place") in image_map:
                                act["image"] = image_map[act["place"]]
                elif plan_dict.get("time_slots"):
                    for slot in plan_dict["time_slots"]:
                        for act in slot.get("activities", []):
                            if act.get("place") in image_map:
                                act["image"] = image_map[act["place"]]
            except Exception as e:
                logger.warning(f"Error resolving place images for itinerary: {e}")

        # 6. Generate rich standardized Markdown Table
        markdown_table = self._generate_markdown_table(plan_dict)
        plan_dict["markdown_table"] = markdown_table

        # 7. Construct rich human-readable markdown for legacy / text clients
        prose_markdown = (
            f"# Curated Itinerary: {plan_dict.get('destination', dest)}\n\n"
            f"**Total Duration**: {plan_dict.get('total_duration', duration)} | "
            f"**Estimated Budget**: {plan_dict.get('estimated_total_budget', plan_budget)}\n"
            f"**Recommended Stay Zone**: {plan_dict.get('stay_area', stay_pref)}\n\n"
            f"### Trip Summary\n{plan_dict.get('summary', '')}\n\n"
            f"### Schedule & Activity Timeline\n\n{markdown_table}\n\n"
            f"### Estimated Budget Allocation\n"
        )
        if plan_dict.get("budget_breakdown"):
            for cat, amount in plan_dict["budget_breakdown"].items():
                prose_markdown += f"- **{cat.capitalize()}**: {amount}\n"

        # 8. Assemble recommended POI cards
        rec_places = (food_items + market_items + gem_items)[:10]
        rec_attractions = attraction_items[:10]
        all_rec_items = rec_places + rec_attractions
        if all_rec_items:
            try:
                await place_image_resolver.resolve_places_batch(all_rec_items, city=dest, timeout=2.0)
            except Exception as e:
                logger.debug(f"Failed resolving recommendation POI images: {e}")

        return {
            "location": dest,
            "itinerary": prose_markdown,
            "recommended_places": rec_places,
            "recommended_attractions": rec_attractions,
            "plan": plan_dict,
            "parsed_requirements": intent
        }

itinerary_service = ItineraryService()
