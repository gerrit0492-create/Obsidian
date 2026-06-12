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
        "available": "Available for a new challenge",
        "headline": "I make the cost price a number you can build on — quotes that win, margins that hold.",
        "tagline": (
            "Experienced cost engineer in high-tech manufacturing. I turn engineering into "
            "cost prices that stand up to scrutiny, make quoting faster and more "
            "transparent, and protect margin — shoulder to shoulder with engineering, "
            "purchasing, sales and business control."
        ),
        "cta_contact": "Get in touch",
        "cta_cv": "Download CV",
        "nav": ["About", "Strengths", "Impact", "Projects", "Experience", "Contact"],

        "about_title": "About me",
        "about": (
            "My career runs from the shop floor to the calculation office — DAF Trucks, "
            "VDL ETG, Andritz, Wilting and Wärtsilä — so when I put a cost price on paper, "
            "I know what sits behind every operation. That's the difference: I don't "
            "estimate from a distance. I translate technical choices into clear cost "
            "impact, keep quoting fast and transparent, and get engineering, purchasing, "
            "sales and business control onto one and the same number — so discussions are "
            "about decisions, not about whose figure is right. Where the tooling falls "
            "short, I build it myself — data & dashboards (Power BI), automation & tools "
            "(Python), SAP, Excel/VBA — so every calculation gets sharper than the last. "
            "Lean Six Sigma Green Belt; hands-on, curious and pragmatic. I'm looking for a "
            "cost engineer or estimator role where a reliable cost price genuinely moves "
            "the business."
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
            {"metric": "Numbers that hold", "title": "From first quote to post-calculation",
             "text": "Cost prices that survive scrutiny — for development, customer and non-standard projects. Sales quotes with confidence, business control closes without surprises, and margin stays where it belongs."},
            {"metric": "One shared number", "title": "Four departments, one cost price",
             "text": "I get engineering, purchasing, sales and business control working from the same figure — fewer debates about the number, more decisions built on it."},
            {"metric": "High-tech proven", "title": "DAF · VDL ETG · Andritz · Wilting · Wärtsilä",
             "text": "Cost and manufacturing experience earned at leading manufacturers — I speak the language of the shop floor and the boardroom, and translate between the two."},
        ],

        "projects_title": "Selected work",
        "projects": [
            {
                "title": "Pre/post calculation model — Wärtsilä",
                "text": "Built hand in hand with business control in Power BI: budgeted and actual cost side by side, with deviations visible while there is still time to act. Month-end surprises became early signals — and conversations about cost became calmer and sharper.",
                "tags": ["Power BI", "Cost control", "SAP"],
                "link": "",
            },
            {
                "title": "Cost-Forge — estimating tool",
                "text": "An estimating tool I designed and built myself: BOM import, routings, market data, surcharges, quote export (PDF/Excel) and management dashboards. The result: quoting that is faster, consistent from estimator to estimator, and easy to defend in front of a customer.",
                "tags": ["Python", "Estimating", "Dashboards"],
                "link": "",
            },
            {
                "title": "Energy cost dashboard",
                "text": "Because cost transparency is a habit, not a job title: a home-built dashboard that turns raw energy and charging data into cost per car, monthly trends and day/night tariff insight, with live meter readings and Excel/PDF export.",
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
            {"period": "", "org": "DAF Trucks", "role": "Production/Technical Engineer & Team Lead"},
        ],

        "contact_title": "Let's talk",
        "contact_text": (
            "Need someone who makes the cost price dependable, the quoting faster and the "
            "margin conversation easier? I'd love to hear from you — send me an email or "
            "connect on LinkedIn. I respond quickly, and I'm happy to walk you through "
            "real examples of my work."
        ),
        "footer": "© 2026 Gerrit Düthler · Eindhoven",
    },

    "nl": {
        "role": "Cost Engineer · Calculator · Werkvoorbereider",
        "available": "Beschikbaar voor een nieuwe uitdaging",
        "headline": "Ik maak van de kostprijs een cijfer waar je op kunt bouwen — offertes die winnen, marges die staan.",
        "tagline": (
            "Ervaren cost engineer in de high-tech maakindustrie. Ik vertaal techniek naar "
            "kostprijzen die elke toets doorstaan, maak offreren sneller en transparanter, "
            "en bescherm de marge — schouder aan schouder met engineering, inkoop, verkoop "
            "en business control."
        ),
        "cta_contact": "Neem contact op",
        "cta_cv": "Download CV",
        "nav": ["Over mij", "Kwaliteiten", "Resultaten", "Projecten", "Ervaring", "Contact"],

        "about_title": "Over mij",
        "about": (
            "Mijn loopbaan loopt van de werkvloer naar de calculatie — DAF Trucks, "
            "VDL ETG, Andritz, Wilting en Wärtsilä — dus als ik een kostprijs op papier "
            "zet, weet ik wat er achter elke bewerking zit. Dat is het verschil: ik "
            "calculeer niet op afstand. Ik vertaal technische keuzes naar helder "
            "kosteneffect, houd offreren snel en transparant, en krijg engineering, "
            "inkoop, verkoop en business control op één en hetzelfde cijfer — zodat het "
            "gesprek over beslissingen gaat, niet over wiens getal klopt. Waar de tooling "
            "tekortschiet, bouw ik die zelf — data & dashboards (Power BI), automatisering "
            "& tools (Python), SAP, Excel/VBA — zodat elke calculatie scherper wordt dan "
            "de vorige. Lean Six Sigma Green Belt; hands-on, nieuwsgierig en pragmatisch. "
            "Ik zoek een rol als cost engineer of calculator waar een betrouwbare "
            "kostprijs het bedrijf echt vooruithelpt."
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
            {"metric": "Cijfers die staan", "title": "Van eerste offerte tot nacalculatie",
             "text": "Kostprijzen die elke toets doorstaan — voor ontwikkel-, klant- en niet-standaard projecten. Verkoop offreert met vertrouwen, business control sluit af zonder verrassingen, en de marge blijft waar die hoort."},
            {"metric": "Eén gedeeld cijfer", "title": "Vier afdelingen, één kostprijs",
             "text": "Ik krijg engineering, inkoop, verkoop en business control aan het werk met hetzelfde getal — minder discussie over het cijfer, meer beslissingen die erop bouwen."},
            {"metric": "High-tech bewezen", "title": "DAF · VDL ETG · Andritz · Wilting · Wärtsilä",
             "text": "Kosten- en productie-ervaring opgedaan bij toonaangevende maakbedrijven — ik spreek de taal van de werkvloer én van de directiekamer, en vertaal tussen die twee."},
        ],

        "projects_title": "Geselecteerd werk",
        "projects": [
            {
                "title": "Pre/post-calculatiemodel — Wärtsilä",
                "text": "Samen met business control gebouwd in Power BI: begrote en werkelijke kosten naast elkaar, met afwijkingen die zichtbaar worden zolang er nog tijd is om bij te sturen. Verrassingen aan het eind van de maand werden vroege signalen — en het gesprek over kosten werd rustiger en scherper.",
                "tags": ["Power BI", "Kostenbeheersing", "SAP"],
                "link": "",
            },
            {
                "title": "Cost-Forge — calculatietool",
                "text": "Een calculatietool die ik zelf ontwierp en bouwde: BOM-import, routings, marktdata, toeslagen, offerte-export (PDF/Excel) en management-dashboards. Het resultaat: offreren dat sneller gaat, consistent is van calculator tot calculator, en goed te verdedigen is tegenover de klant.",
                "tags": ["Python", "Calculatie", "Dashboards"],
                "link": "",
            },
            {
                "title": "Laad-kostendashboard",
                "text": "Omdat kostentransparantie een gewoonte is, geen functietitel: een zelfgebouwd dashboard dat van ruwe energie- en laaddata kosten per auto, maandtrends en inzicht in dal/piek-tarief maakt, met live meteruitlezing en Excel/PDF-export.",
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
            {"period": "", "org": "DAF Trucks", "role": "Production/Technical Engineer & Teamleider"},
        ],

        "contact_title": "Laten we praten",
        "contact_text": (
            "Op zoek naar iemand die de kostprijs betrouwbaar maakt, het offreren versnelt "
            "en het margegesprek makkelijker maakt? Ik hoor graag van je — stuur een mail "
            "of connect op LinkedIn. Ik reageer snel, en laat je graag echte voorbeelden "
            "van mijn werk zien."
        ),
        "footer": "© 2026 Gerrit Düthler · Eindhoven",
    },
}
