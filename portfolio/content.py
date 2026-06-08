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
    "en": {
        "role": "Cost Engineer · Estimator · Manufacturing Engineer",
        "available": "Available for a new role",
        "headline": "I make the cost number trustworthy — so quotes win and margins hold.",
        "tagline": (
            "Cost engineer in high-tech manufacturing. I turn engineering into defensible cost "
            "prices, speed up quoting, and protect margin — working hand in hand with "
            "engineering, purchasing, sales and business control."
        ),
        "cta_contact": "Get in touch",
        "cta_cv": "Download CV",
        "nav": ["About", "Strengths", "Impact", "Projects", "Experience", "Contact"],

        "about_title": "About me",
        "about": (
            "I'm a cost engineer who makes the number something the business can trust. I've spent "
            "my career on the shop floor and in costing — at DAF Trucks, VDL ETG, Andritz, Wilting "
            "and Wärtsilä — so I know where cost really sits and how to take it out without cutting "
            "corners. I translate technical choices into clear cost impact, keep estimating fast "
            "and transparent, and get engineering, purchasing, sales and business control onto the "
            "same number. Lean Six Sigma Green Belt: hands-on, data-driven and pragmatic. Where it "
            "helps, I build the tools (Power BI, SAP, Excel/VBA) that make calculations sharper. "
            "I'm looking for a cost engineer or estimator role where reliable cost and healthy "
            "margin truly matter."
        ),

        "skills_title": "Core strengths",
        "skills": [
            "Cost estimating", "Should-cost", "Post-calculation", "Margin & quote control",
            "Lean Six Sigma (Green Belt)", "Continuous improvement",
            "Work preparation & routing", "Make strategy", "SAP",
            "Data & dashboards (Power BI)", "Excel & VBA", "Automation & tools (Python)",
            "CNC programming", "Cross-functional collaboration", "NL · EN · DE",
        ],

        "highlights_title": "Impact",
        "highlights": [
            {"metric": "Cost you can defend", "title": "Quote to post-calculation",
             "text": "Defensible cost prices across development, customer and non-standard projects — so quotes hold and margins stick."},
            {"metric": "Green Belt", "title": "Lean Six Sigma",
             "text": "Structurally better quality, lead time and cost through hands-on continuous improvement."},
            {"metric": "5", "title": "Leading manufacturers",
             "text": "Hands-on cost and manufacturing experience across DAF, VDL ETG, Andritz, Wilting and Wärtsilä."},
        ],

        "projects_title": "Selected work",
        "projects": [
            {
                "title": "Pre/post calculation model — Wärtsilä",
                "text": "Built with business control in Power BI to track budgeted vs. actual and surface deviations early — turning month-end surprises into signals you can act on.",
                "tags": ["Power BI", "Cost control", "SAP"],
                "link": "",
            },
            {
                "title": "Cost-Forge — estimating tool",
                "text": "A self-built estimating tool: BOM import, routings, market data, surcharges, quote export (PDF/Excel) and management dashboards. Quoting that's faster and consistent.",
                "tags": ["Python", "Estimating", "Dashboards"],
                "link": "",
            },
            {
                "title": "Energy cost dashboard",
                "text": "Turns raw energy/charging data into cost per car, monthly trends and day/night tariff insight, with live meter reads and Excel/PDF export.",
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

        "contact_title": "Let's talk",
        "contact_text": (
            "Looking for someone who makes cost dependable and quoting faster? I'd be glad to talk "
            "— drop me an email or connect on LinkedIn, and I'll get back to you quickly."
        ),
        "footer": "© 2026 Gerrit Düthler · Eindhoven",
    },

    "nl": {
        "role": "Cost Engineer · Calculator · Werkvoorbereider",
        "available": "Beschikbaar voor een nieuwe rol",
        "headline": "Ik maak de kostprijs betrouwbaar — zodat offertes scoren en marges kloppen.",
        "tagline": (
            "Cost engineer in de high-tech maakindustrie. Ik vertaal techniek naar onderbouwde "
            "kostprijzen, versnel het offertetraject en bewaak de marge — schouder aan schouder "
            "met engineering, inkoop, verkoop en business control."
        ),
        "cta_contact": "Neem contact op",
        "cta_cv": "Download CV",
        "nav": ["Over mij", "Kwaliteiten", "Resultaten", "Projecten", "Ervaring", "Contact"],

        "about_title": "Over mij",
        "about": (
            "Ik ben een cost engineer die van de kostprijs een cijfer maakt waar de organisatie op "
            "kan bouwen. Mijn loopbaan speelt zich af op de werkvloer én in de calculatie — bij DAF "
            "Trucks, VDL ETG, Andritz, Wilting en Wärtsilä — dus ik weet waar de kosten echt zitten "
            "en hoe je ze eruit haalt zonder bochten af te snijden. Ik vertaal technische keuzes "
            "naar helder kosteneffect, houd calculeren snel en transparant, en krijg engineering, "
            "inkoop, verkoop en business control op één lijn. Lean Six Sigma Green Belt: hands-on, "
            "datagedreven en pragmatisch. Waar het helpt bouw ik zelf de tools (Power BI, SAP, "
            "Excel/VBA) die calculaties scherper maken. Ik zoek een rol als cost engineer of "
            "calculator waarin betrouwbare kosten en een gezonde marge er echt toe doen."
        ),

        "skills_title": "Kernkwaliteiten",
        "skills": [
            "Kostencalculatie", "Should-cost", "Nacalculatie", "Marge- & offertebewaking",
            "Lean Six Sigma (Green Belt)", "Continu verbeteren",
            "Werkvoorbereiding & routing", "Maakstrategie", "SAP",
            "Data & dashboards (Power BI)", "Excel & VBA", "Automatisering & tools (Python)",
            "CNC-programmeren", "Samenwerken over afdelingen", "NL · EN · DE",
        ],

        "highlights_title": "Resultaten",
        "highlights": [
            {"metric": "Onderbouwde kostprijs", "title": "Van offerte tot nacalculatie",
             "text": "Betrouwbare kostprijzen voor ontwikkel-, klant- en niet-standaard projecten — zodat offertes kloppen en marges blijven staan."},
            {"metric": "Green Belt", "title": "Lean Six Sigma",
             "text": "Structureel betere kwaliteit, levertijd en kosten door hands-on continu verbeteren."},
            {"metric": "5", "title": "Toonaangevende maakbedrijven",
             "text": "Praktijkervaring in kosten en productie bij DAF, VDL ETG, Andritz, Wilting en Wärtsilä."},
        ],

        "projects_title": "Geselecteerd werk",
        "projects": [
            {
                "title": "Pre/post-calculatiemodel — Wärtsilä",
                "text": "Met business control opgezet in Power BI om begroot vs. werkelijk te bewaken en afwijkingen vroeg te signaleren — verrassingen aan het eind van de maand werden signalen om op te sturen.",
                "tags": ["Power BI", "Kostenbeheersing", "SAP"],
                "link": "",
            },
            {
                "title": "Cost-Forge — calculatietool",
                "text": "Zelf gebouwde calculatietool: BOM-import, routings, marktdata, toeslagen, offerte-export (PDF/Excel) en management-dashboards. Calculeren dat sneller en consistenter is.",
                "tags": ["Python", "Calculatie", "Dashboards"],
                "link": "",
            },
            {
                "title": "Laad-kostendashboard",
                "text": "Maakt van ruwe energie-/laaddata kosten per auto, maandtrends en inzicht in dal/piek-tarief, met live meteruitlezing en Excel/PDF-export.",
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

        "contact_title": "Laten we praten",
        "contact_text": (
            "Op zoek naar iemand die kosten betrouwbaar en offertes sneller maakt? Ik ga graag in "
            "gesprek — mail me of connect op LinkedIn, ik reageer snel."
        ),
        "footer": "© 2026 Gerrit Düthler · Eindhoven",
    },
}
