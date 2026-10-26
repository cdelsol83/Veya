"""Canned model answers for MOGUL_DEMO=1: lets you run the whole pipeline offline.

All entries are fictional placeholders (sources point at example.com). Never deploy demo pages.
"""
import json
import random
import re

CITIES = ["Asheville, NC", "Moab, UT", "Bend, OR", "Flagstaff, AZ", "Traverse City, MI",
          "Bar Harbor, ME", "Boulder, CO", "Chattanooga, TN", "Sedona, AZ", "Duluth, MN",
          "Lake Tahoe, CA", "Bozeman, MT"]
WORDS = ["Pine", "Cedar", "River", "Bluff", "Hollow", "Ridge", "Meadow", "Falls", "Creek",
         "Aspen", "Granite", "Willow", "Juniper", "Elk", "Fox", "Heron", "Sage", "Copper"]
VENDORS = ["Hipcamp", "KOA", "Recreation.gov", "ReserveAmerica", ""]


def answer(prompt):
    if "Group them into" in prompt:
        return json.dumps(scout())
    if "Propose" in prompt and "page titles" in prompt:
        n = int(re.search(r"Propose (\d+)", prompt).group(1))
        existing = prompt
        titles = [f"Dog-friendly campgrounds near {c}" for c in CITIES if c not in existing]
        return json.dumps(titles[:n])
    if "collect" in prompt and "real entries" in prompt:
        return json.dumps(research(re.search(r'Page: "(.+?)"', prompt).group(1)))
    if "Write the body" in prompt:
        title = re.search(r'titled "(.+?)"', prompt).group(1)
        records = json.loads(prompt.split("fact not present in it:\n", 1)[1].split("\nStructure", 1)[0])
        return body(title, records)
    if "published phone number" in prompt:
        names = re.findall(r"^- (.+?) \(", prompt, re.M)
        return json.dumps([{"name": n, "website": "https://example.com/demo/site", "phone": "(555) 010-0000"}
                           for n in names])
    if "affiliate or referral programs" in prompt:
        return json.dumps(programs())
    if "partnership email" in prompt:
        vendor = re.search(r"partnerships team at (.+?)\. Facts", prompt, re.S).group(1)
        return json.dumps({"subject": f"Referral partnership with {vendor}?",
                           "body": f"Hi {vendor} team,\n\nI run a small directory of dog-friendly "
                                   f"campgrounds that lists {vendor} properties with their pet rules "
                                   "and fees. Do you offer a referral or affiliate arrangement? If so, "
                                   "I'd love to hear the terms.\n\nThanks!"})
    raise ValueError("demo has no canned answer for this prompt")


def research(title):
    rng = random.Random(title)
    city = title.split("near ")[-1]
    records = []
    for i in range(rng.randint(6, 9)):
        name = f"{rng.choice(WORDS)} {rng.choice(WORDS)} {rng.choice(['Campground', 'RV Park', 'Camp', 'State Park'])}"
        records.append({
            "name": f"[Demo] {name}",
            "location": f"{rng.randint(3, 40)} mi from {city}",
            "facts": {
                "pet_fee": rng.choice(["Free", "$5/night", "$10/stay", "$15/night", "unknown"]),
                "max_dogs": rng.choice(["1", "2", "3", "No limit"]),
                "leash_rule": rng.choice(["6 ft leash", "10 ft leash", "Off-leash area", "Leashed at all times"]),
                "breed_limits": rng.choice(["None", "Some breeds restricted", "unknown"]),
                "nightly_from": f"${rng.randint(18, 75)}",
                "season": rng.choice(["Year-round", "Apr-Oct", "May-Sep", "Mar-Nov"]),
            },
            "vendor": rng.choice(VENDORS),
            "website": f"https://example.com/demo/{re.sub('[^a-z]+', '-', name.lower())}-site",
            "phone": f"(555) {rng.randint(200, 999)}-{rng.randint(1000, 9999)}",
            "source": f"https://example.com/demo/{re.sub('[^a-z]+', '-', name.lower())}",
        })
    return {"description": f"{len(records)} dog-friendly campgrounds near {city}, with pet fees, "
                           "leash rules and dog limits checked against each campground's own page.",
            "records": records}


def body(title, records):
    city = title.split("near ")[-1]
    cheapest = min(records, key=lambda r: int(r["facts"]["nightly_from"].strip("$")))
    free = [r for r in records if r["facts"]["pet_fee"] == "Free"]
    offleash = [r for r in records if r["facts"]["leash_rule"] == "Off-leash area"]
    multi = [r for r in records if r["facts"]["max_dogs"] in ("3", "No limit")]
    lines = [
        f"Looking for somewhere to camp with your dog around {city}? We checked {len(records)} "
        f"campgrounds and recorded what actually matters: the pet fee, how many dogs you can bring, "
        f"leash rules and any breed limits. {cheapest['name']} is the cheapest base at "
        f"{cheapest['facts']['nightly_from']} a night.",
        "", "## How we picked", "",
        f"Every campground near {city} on this page links to the page where we verified its pet "
        "policy. Rules change, so check that page before you book, and tell us if something is out of date.",
        "", "## At a glance", "",
        f"- **Lowest nightly rate listed:** {cheapest['facts']['nightly_from']} ({cheapest['name']}).",
        f"- **No pet fee:** {', '.join(r['name'] for r in free) or 'none of the campgrounds checked'}.",
        f"- **Allow 3 or more dogs:** {', '.join(r['name'] for r in multi) or 'none of the campgrounds checked'}.",
        "", "## Things to know before you go", "",
    ]
    for r in records:
        f = r["facts"]
        lines.append(f"- **{r['name']}** ({r['location']}) is open {f['season'].lower()}, charges "
                     f"{f['pet_fee'].lower()} for pets, allows {f['max_dogs'].lower()} dogs per site and "
                     f"requires {f['leash_rule'].lower()}; breed limits: {f['breed_limits'].lower()}.")
    lines += [
        "", "## FAQ", "",
        f"### Are there free dog-friendly campgrounds near {city}?",
        (f"Yes: {', '.join(r['name'] for r in free)} charge no pet fee." if free
         else f"None of the {len(records)} we checked near {city} waive the pet fee entirely."),
        "", f"### Can my dog be off-leash at campgrounds near {city}?",
        (f"Only in designated areas, for example at {offleash[0]['name']}." if offleash
         else f"Not at any of the campgrounds we checked near {city}; plan on a leash."),
        "", f"### When is the best season to camp with a dog near {city}?",
        f"Most campgrounds here run {records[-1]['facts']['season'].lower()}; book early for summer weekends.",
    ]
    return "\n".join(lines)


def scout():
    base = [
        ("Dog-friendly campgrounds by city", 8, 7, 7, 6, 7),
        ("Free passport photo locations", 7, 8, 3, 7, 6),
        ("Self-storage prices by zip code", 6, 8, 8, 4, 5),
        ("Software alternatives for landscapers", 5, 5, 9, 7, 8),
        ("Notary public hours near me", 6, 7, 3, 6, 5),
    ]
    keys = ["complaint_volume", "search_demand", "monetization", "weak_competition", "data_available"]
    return [{"niche": n, **dict(zip(keys, s)),
             "example_complaints": [f'"why is it so hard to find {n.lower()}" https://example.com/demo-post'],
             "page_ideas": [f"{n} #{i}" for i in range(1, 6)],
             "affiliate_angles": ["Demo program"], "data_sources": ["Official listings"]} for n, *s in base]


def programs():
    return [
        {"name": "Hipcamp", "network": "Impact", "signup_url": "https://example.com/demo/hipcamp-affiliates",
         "commission": "unknown", "cookie_days": "unknown", "type": "self_serve", "contact_email": "",
         "source": "https://example.com/demo"},
        {"name": "Demo Pet Gear Co", "network": "in-house", "signup_url": "",
         "commission": "unknown", "cookie_days": "unknown", "type": "contact",
         "contact_email": "partners@example.com", "source": "https://example.com/demo"},
    ]
