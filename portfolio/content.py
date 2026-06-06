"""Edit your portfolio here — all text lives in this one file.

Two languages: "nl" (Nederlands) and "en" (English). Keep the same structure in
both. Anything between ‹ › is a placeholder for you to replace. Coach tips are in
the comments.

Privacy note: a public portfolio should NOT show your home address, birth date or
phone number. We keep just city + a professional email + links.
"""

PROFILE = {
    "name": "Gerrit Düthler",
    "photo": "assets/photo.jpg",      # optional; drop a square photo here
    "cv_file": "assets/cv.pdf",       # optional; a CLEAN pdf CV (no address/DOB) enables the download
    "email": "gerrit@duthler.info",
    "linkedin": "https://www.linkedin.com/in/‹jouw-profiel›",  # ← vul je LinkedIn-URL in
    "github": "https://github.com/gerrit0492-create",
    "location": "Eindhoven, Nederland",
}

CONTENT = {
    "nl": {
        "role": "Cost Engineer · Calculator · Werkvoorbereider",
        "tagline": "Ik vertaal techniek naar kosten — en bouw de tools die calculaties sneller, scherper en transparanter maken.",
        "cta_contact": "Neem contact op",
        "cta_cv": "Download CV",
        "nav": ["Over mij", "Kwaliteiten", "Resultaten", "Projecten", "Ervaring", "Contact"],

        "about_title": "Over mij",
        "about": (
            "Cost engineer met 35+ jaar ervaring in de maakindustrie — van DAF Trucks en "
            "VDL ETG tot Andritz en Wärtsilä. Ik combineer diep technisch inzicht met data "
            "en automatisering: ik bouw mijn eigen tools (van Excel/SAP tot Python-dashboards) "
            "die handwerk wegnemen en betere kostenbeslissingen mogelijk maken. Lean Six Sigma "
            "Green Belt. Ik zoek een rol die aansluit op mijn ervaring — cost engineer, calculator "
            "of werkvoorbereider — waarin ik calculatie en kostenbeheersing naar een hoger niveau til."
        ),

        "skills_title": "Kernkwaliteiten",
        "skills": [
            "Kostencalculatie", "Should-cost", "Nacalculatie", "Lean Six Sigma (Green Belt)",
            "DMAIC · Kaizen · 5S · FMEA", "Werkvoorbereiding & routing", "Maakstrategie",
            "SAP", "Power BI", "Excel & VBA", "Python", "Streamlit-dashboards", "CNC-programmeren",
            "Procesverbetering", "Coachen & leidinggeven", "NL · EN · DE",
        ],

        "highlights_title": "Resultaten",
        # Coach: vervang ‹x› door echte cijfers waar je kunt — dat maakt het sterk.
        "highlights": [
            {"metric": "35+ jr", "title": "Maakindustrie & kostentechniek", "text": "Brede ervaring bij DAF, VDL ETG, Andritz, Wilting en Wärtsilä."},
            {"metric": "2 modellen", "title": "Kostenmodellen @ Wärtsilä", "text": "Nacalculatie- en kostenopvolgingsmodel opgezet samen met business control."},
            {"metric": "€195k", "title": "Fout opgespoord", "text": "Via mijn zelfgebouwde pre/post-model (Power BI) een quantity-fout gevonden: een korting van €195k die niet was meegenomen."},
        ],

        "projects_title": "Projecten",
        "projects": [
            {
                "title": "Cost-Forge — calculatietool",
                "text": "Eigen Streamlit-tool voor kostencalculatie: BOM-import, routings, marktdata, toeslagen, offerte-export (PDF/Excel) en management-dashboards.",
                "tags": ["Python", "Streamlit", "Calculatie"],
                "link": "https://github.com/gerrit0492-create/cost-forge-2",
            },
            {
                "title": "Laad-kostendashboard",
                "text": "Dashboard over EV-laaddata: kosten per auto, maandtrends, dal/piek-tarief, live P1- en laadpaal-uitlezing, Excel/PDF-export.",
                "tags": ["Python", "Streamlit", "Data"],
                "link": "https://github.com/gerrit0492-create/obsidian",
            },
            {
                "title": "Pre/post-calculatiemodel (Wärtsilä)",
                "text": "Pre/post-calculatiemodel in Power BI, opgezet met business control om begroot vs. werkelijk te bewaken — spoorde o.a. een gemiste korting van €195k op.",
                "tags": ["Power BI", "Kosten", "SAP"],
                "link": "",
            },
        ],

        "experience_title": "Ervaring",
        "experience": [
            {"period": "2021 – 2026", "org": "Wärtsilä", "role": "Cost Engineer"},
            {"period": "2019 – 2021", "org": "Wilting", "role": "Manufacturing Engineer"},
            {"period": "2017 – 2019", "org": "VDL ETG", "role": "Factory Engineer"},
            {"period": "2011 – 2017", "org": "Andritz Feed & Biofuel", "role": "Supervisor productie"},
            {"period": "1987 – 2011", "org": "DAF Trucks", "role": "Production/Technical Engineer & Teamleider"},
        ],

        "contact_title": "Contact",
        "contact_text": "Interesse? Ik kom graag in gesprek. Mail me of bekijk mijn LinkedIn en GitHub.",
        "footer": "Gemaakt met Streamlit",
    },

    "en": {
        "role": "Cost Engineer · Estimator · Manufacturing Engineer",
        "tagline": "I translate engineering into cost — and build the tools that make estimating faster, sharper and more transparent.",
        "cta_contact": "Get in touch",
        "cta_cv": "Download CV",
        "nav": ["About", "Strengths", "Impact", "Projects", "Experience", "Contact"],

        "about_title": "About me",
        "about": (
            "Cost engineer with 35+ years in manufacturing — from DAF Trucks and VDL ETG to "
            "Andritz and Wärtsilä. I combine deep technical insight with data and automation: "
            "I build my own tools (from Excel/SAP to Python dashboards) that remove manual work "
            "and enable better cost decisions. Lean Six Sigma Green Belt. I'm looking for a role that "
            "fits my experience — cost engineer, estimator or manufacturing engineer — where I can take "
            "estimating and cost control to the next level."
        ),

        "skills_title": "Core strengths",
        "skills": [
            "Cost estimating", "Should-cost", "Post-calculation", "Lean Six Sigma (Green Belt)",
            "DMAIC · Kaizen · 5S · FMEA", "Work preparation & routing", "Make strategy",
            "SAP", "Power BI", "Excel & VBA", "Python", "Streamlit dashboards", "CNC programming",
            "Process improvement", "Coaching & leadership", "NL · EN · DE",
        ],

        "highlights_title": "Impact",
        "highlights": [
            {"metric": "35+ yrs", "title": "Manufacturing & cost engineering", "text": "Broad experience at DAF, VDL ETG, Andritz, Wilting and Wärtsilä."},
            {"metric": "2 models", "title": "Cost models @ Wärtsilä", "text": "Post-calculation and cost-follow-up models built together with business control."},
            {"metric": "€195k", "title": "Error caught", "text": "My self-built pre/post model (Power BI) flagged a quantity error — a €195k discount that had been missed."},
        ],

        "projects_title": "Projects",
        "projects": [
            {
                "title": "Cost-Forge — estimating tool",
                "text": "My own Streamlit tool for cost estimating: BOM import, routings, market data, surcharges, quote export (PDF/Excel) and management dashboards.",
                "tags": ["Python", "Streamlit", "Estimating"],
                "link": "https://github.com/gerrit0492-create/cost-forge-2",
            },
            {
                "title": "EV charging cost dashboard",
                "text": "Dashboard over EV charging data: cost per car, monthly trends, day/night tariff, live P1 and charger reads, Excel/PDF export.",
                "tags": ["Python", "Streamlit", "Data"],
                "link": "https://github.com/gerrit0492-create/obsidian",
            },
            {
                "title": "Pre/post calculation model (Wärtsilä)",
                "text": "A pre/post calculation model in Power BI, set up with business control to track budgeted vs. actual — and it flagged a missed €195k discount.",
                "tags": ["Power BI", "Cost", "SAP"],
                "link": "",
            },
        ],

        "experience_title": "Experience",
        "experience": [
            {"period": "2021 – 2026", "org": "Wärtsilä", "role": "Cost Engineer"},
            {"period": "2019 – 2021", "org": "Wilting", "role": "Manufacturing Engineer"},
            {"period": "2017 – 2019", "org": "VDL ETG", "role": "Factory Engineer"},
            {"period": "2011 – 2017", "org": "Andritz Feed & Biofuel", "role": "Production Supervisor"},
            {"period": "1987 – 2011", "org": "DAF Trucks", "role": "Production/Technical Engineer & Team Lead"},
        ],

        "contact_title": "Contact",
        "contact_text": "Interested? I'd be glad to talk. Email me or check my LinkedIn and GitHub.",
        "footer": "Built with Streamlit",
    },
}
