"""Edit your portfolio here — all text lives in this one file.

Two languages: "nl" (Nederlands) and "en" (English). Keep the same structure in
both. Anything between ‹ › is a placeholder for you to replace.

Privacy note: a public portfolio should NOT show your home address, birth date or
phone number. We keep just city + a professional email + LinkedIn.
"""

PROFILE = {
    "name": "Gerrit Düthler",
    "photo": "assets/photo.jpg",      # optional; drop a square photo here
    "cv_file": "assets/cv.pdf",       # clean pdf CV (no address/DOB) — enables the download
    "email": "gerrit@duthler.info",
    "linkedin": "https://www.linkedin.com/in/gerrit-d-90a50234",
    "location": "Eindhoven, Nederland",
}

CONTENT = {
    "nl": {
        "role": "Cost Engineer · Calculator · Werkvoorbereider",
        "available": "Beschikbaar voor een nieuwe rol",
        "tagline": "Ik vertaal techniek naar betrouwbare kostprijzen en houd kosten beheersbaar — van offerte tot nacalculatie.",
        "cta_contact": "Neem contact op",
        "cta_cv": "Download CV",
        "nav": ["Over mij", "Kwaliteiten", "Resultaten", "Projecten", "Ervaring", "Contact"],

        "about_title": "Over mij",
        "about": (
            "Cost engineer met 35+ jaar in de maakindustrie — DAF, VDL ETG, Andritz, Wilting "
            "en Wärtsilä. Ik ken het product én de werkvloer en vertaal dat naar onderbouwde "
            "kostprijzen, in nauwe samenwerking met engineering, inkoop, verkoop en business "
            "control. Lean Six Sigma Green Belt. Waar nodig pak ik zelf data en tooling "
            "(Power BI, SAP) op om calculaties te verscherpen. Ik zoek een rol als cost "
            "engineer, calculator of werkvoorbereider waarin ik calculatie en kostenbeheersing "
            "aantoonbaar verbeter."
        ),

        "skills_title": "Kernkwaliteiten",
        "skills": [
            "Kostencalculatie", "Should-cost", "Nacalculatie", "Lean Six Sigma (Green Belt)",
            "DMAIC · Kaizen · 5S · FMEA", "Werkvoorbereiding & routing", "Maakstrategie",
            "SAP", "Power BI", "Excel & VBA", "Python", "CNC-programmeren",
            "Procesverbetering", "Coachen & leidinggeven", "NL · EN · DE",
        ],

        "highlights_title": "Resultaten",
        "highlights": [
            {"metric": "35+ jr", "title": "Kostentechniek in de maakindustrie", "text": "Calculaties voor ontwikkel-, klant- en niet-standaard projecten, van offerte tot nacalculatie."},
            {"metric": "Green Belt", "title": "Lean Six Sigma", "text": "Structureel betere kwaliteit, levertijd én kosten via DMAIC, Kaizen, 5S en FMEA."},
            {"metric": "+", "title": "Data & tooling (extra)", "text": "Pakt waar nodig zelf modellen op (o.a. pre/post-calculatie) om begroot versus werkelijk transparant te maken."},
        ],

        "projects_title": "Projecten",
        "projects": [
            {
                "title": "Pre/post-calculatiemodel (Wärtsilä)",
                "text": "Pre/post-calculatiemodel in Power BI, opgezet met business control om begroot vs. werkelijk te bewaken en afwijkingen vroeg te signaleren.",
                "tags": ["Power BI", "Kosten", "SAP"],
                "link": "",
            },
            {
                "title": "Cost-Forge — calculatietool",
                "text": "Eigen calculatietool: BOM-import, routings, marktdata, toeslagen, offerte-export (PDF/Excel) en management-dashboards.",
                "tags": ["Python", "Calculatie", "Dashboards"],
                "link": "",
            },
            {
                "title": "Laad-kostendashboard",
                "text": "Dashboard over energie-/laaddata: kosten per auto, maandtrends, dal/piek-tarief en live meteruitlezing met Excel/PDF-export.",
                "tags": ["Python", "Data", "Excel"],
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
        "contact_text": "Interesse? Ik kom graag in gesprek. Mail me of bekijk mijn LinkedIn.",
        "footer": "Gemaakt met Streamlit",
    },

    "en": {
        "role": "Cost Engineer · Estimator · Manufacturing Engineer",
        "available": "Available for a new role",
        "tagline": "I turn engineering into reliable cost prices and keep costs in control — from quote to post-calculation.",
        "cta_contact": "Get in touch",
        "cta_cv": "Download CV",
        "nav": ["About", "Strengths", "Impact", "Projects", "Experience", "Contact"],

        "about_title": "About me",
        "about": (
            "Cost engineer with 35+ years in manufacturing — DAF, VDL ETG, Andritz, Wilting "
            "and Wärtsilä. I know the product and the shop floor and translate both into "
            "well-founded cost prices, working closely with engineering, purchasing, sales and "
            "business control. Lean Six Sigma Green Belt. Where useful I build my own data and "
            "tooling (Power BI, SAP) to sharpen the numbers. I'm looking for a cost engineer, "
            "estimator or manufacturing-engineer role where I measurably improve estimating and "
            "cost control."
        ),

        "skills_title": "Core strengths",
        "skills": [
            "Cost estimating", "Should-cost", "Post-calculation", "Lean Six Sigma (Green Belt)",
            "DMAIC · Kaizen · 5S · FMEA", "Work preparation & routing", "Make strategy",
            "SAP", "Power BI", "Excel & VBA", "Python", "CNC programming",
            "Process improvement", "Coaching & leadership", "NL · EN · DE",
        ],

        "highlights_title": "Impact",
        "highlights": [
            {"metric": "35+ yrs", "title": "Cost engineering in manufacturing", "text": "Calculations for development, customer and non-standard projects, from quote to post-calculation."},
            {"metric": "Green Belt", "title": "Lean Six Sigma", "text": "Structurally better quality, lead time and cost via DMAIC, Kaizen, 5S and FMEA."},
            {"metric": "+", "title": "Data & tooling (extra)", "text": "Builds models where useful (e.g. pre/post calculation) to make budget-vs-actual transparent."},
        ],

        "projects_title": "Projects",
        "projects": [
            {
                "title": "Pre/post calculation model (Wärtsilä)",
                "text": "A pre/post calculation model in Power BI, set up with business control to track budgeted vs. actual and surface deviations early.",
                "tags": ["Power BI", "Cost", "SAP"],
                "link": "",
            },
            {
                "title": "Cost-Forge — estimating tool",
                "text": "My own estimating tool: BOM import, routings, market data, surcharges, quote export (PDF/Excel) and management dashboards.",
                "tags": ["Python", "Estimating", "Dashboards"],
                "link": "",
            },
            {
                "title": "Energy cost dashboard",
                "text": "Dashboard over energy/charging data: cost per car, monthly trends, day/night tariff and live meter reads with Excel/PDF export.",
                "tags": ["Python", "Data", "Excel"],
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
        "contact_text": "Interested? I'd be glad to talk. Email me or check my LinkedIn.",
        "footer": "Built with Streamlit",
    },
}
