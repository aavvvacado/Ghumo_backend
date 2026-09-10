---
layout: docs
title: AI Itinerary Planner
nav_order: 6
---

# AI Itinerary Planner

The **Ghumo AI Itinerary Planner** generates customized, contextual travel itineraries. It supports both free-form natural language prompts and structured field constraints, segregate activities into day chunks or time slots, outputs ready-to-render Markdown tables, and resolves verified photography for all suggested landmarks.

---

## Core Capabilities

### 1. Conversational Prompt Parsing
Instead of requiring users to fill out multiple strict dropdowns, the planner accepts natural conversational sentences:
- *"I am visiting Goa for 3 days with a 10000 budget"*
- *"visiting Chandni Chowk for 4 hours in the afternoon"*
- *"planning a weekend trip to Udaipur on low budget"*

Gemini AI parses the intent and infers realistic, practical defaults for anything omitted (interests, stay neighborhoods, pacing) rather than returning validation errors.

---

### 2. Intelligent Segregation Modes

The planner automatically selects between two chunking modes based on trip duration:

| Mode | Trigger Condition | Structure & Organization |
| :--- | :--- | :--- |
| `day_wise` | Multi-day trips (e.g., 2 days, 3 days, 1 week) | Organizes activities by **Day 1**, **Day 2**, etc. Each day includes a distinct theme, stay recommendation, day cost estimate, and scheduled activities. |
| `time_wise` | Same-day or hourly trips (e.g., 4 hours, afternoon) | Organizes activities into **Morning**, **Afternoon**, **Evening**, and **Night** slots with precise time bounds. |

---

### 3. Standardized Markdown Table

Every response includes a pre-formatted Markdown table in `plan["markdown_table"]` that can be directly rendered in Flutter, React, or Markdown viewers:

| Timing / Slot | Place / Landmark | Duration | Purpose & Highlights | Estimated Cost |
| :--- | :--- | :--- | :--- | :--- |
| **DAY 1: Heritage & Royal Architecture** | | | | |
| 09:00 AM - 11:30 AM | **Hawa Mahal** | 2.5 hours | Sightseeing, photography & palace facade | ₹100 |
| 12:00 PM - 02:00 PM | **City Palace, Jaipur** | 2 hours | Royal museum galleries & courtyard exploration | ₹300 |
| 02:30 PM - 03:30 PM | **LMB (Laxmi Misthan Bhandar)** | 1 hour | Authentic Rajasthani thali & sweets | ₹500 |

---

### 4. Categorized Budget Breakdown

Plans include estimated expense allocations across four core buckets:
- **Stay**: Recommended hotel or guesthouse budget.
- **Food**: Local dining, cafes, and street food.
- **Activities**: Entry tickets, monuments, and guided experiences.
- **Transport**: Cabs, autos, or metro transit.

---

### 5. Zero-Hallucination Image Resolution

Each place suggested in the itinerary undergoes batch image resolution via [place_image_resolver.py](file:///c:/Users/ashki/OneDrive/Documents/Ghumo/ghumo_backend/app/services/place_image_resolver.py). Images are matched with verified Wikimedia Commons / Wikidata or Unsplash assets, complete with licensing and attribution metadata.

---

## Example Usage

### Python / Requests
```python
import httpx
import asyncio

async def plan():
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "http://localhost:8000/itinerary",
            json={"prompt": "3 days in Varanasi focused on spirituality and street food with 6000 INR budget"}
        )
        plan_data = res.json()
        print("Itinerary Table:\n", plan_data["plan"]["markdown_table"])

asyncio.run(plan())
```
