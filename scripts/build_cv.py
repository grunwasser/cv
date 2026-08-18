#!/usr/bin/env python3
"""Génère tous les formats du CV depuis cv.yml."""

from __future__ import annotations

import argparse
from datetime import date
from html import escape
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from textwrap import indent
from urllib.parse import urljoin

import yaml


ROOT = Path(__file__).resolve().parent.parent
MONTHS = {
    "01": "janvier", "02": "février", "03": "mars", "04": "avril",
    "05": "mai", "06": "juin", "07": "juillet", "08": "août",
    "09": "septembre", "10": "octobre", "11": "novembre", "12": "décembre",
}


def validate_data(data: dict) -> None:
    errors: list[str] = []
    required_sections = ("meta", "person", "profile", "experiences", "skills", "certifications", "education", "languages", "interests")
    for section in required_sections:
        if not data.get(section):
            errors.append(f"section obligatoire absente ou vide : {section}")

    person = data.get("person", {})
    for field in (
        "first_name", "last_name", "birth_date", "title", "professional_title", "eyebrow",
        "email", "location", "photo", "appointment_url", "appointment_description",
    ):
        if not person.get(field):
            errors.append(f"champ obligatoire absent : person.{field}")
    if person.get("birth_date") and not isinstance(person["birth_date"], date):
        errors.append("person.birth_date doit utiliser le format YYYY-MM-DD sans guillemets")
    if "show_age" in person and not isinstance(person["show_age"], bool):
        errors.append("person.show_age doit être true ou false")
    if "show_qr_code" in person and not isinstance(person["show_qr_code"], bool):
        errors.append("person.show_qr_code doit être true ou false")
    if "phone_pdf_only" in person and not isinstance(person["phone_pdf_only"], bool):
        errors.append("person.phone_pdf_only doit être true ou false")
    if person.get("email") and "@" not in person["email"]:
        errors.append("person.email n'est pas une adresse valide")
    photo = Path(text(person.get("photo")))
    if photo.is_absolute() or ".." in photo.parts:
        errors.append("person.photo doit être un chemin relatif situé dans le projet")
    if bool(person.get("phone_display")) != bool(person.get("phone_uri")):
        errors.append("person.phone_display et person.phone_uri doivent être tous les deux remplis ou tous les deux vides")
    allowed_availability = {None, "", "En recherche active", "Ouvert aux opportunités", "Non disponible actuellement"}
    if person.get("availability") not in allowed_availability:
        errors.append("person.availability doit être vide, En recherche active, Ouvert aux opportunités ou Non disponible actuellement")
    for index, profile_item in enumerate(person.get("profiles", []), start=1):
        if not profile_item.get("network") or not profile_item.get("url"):
            errors.append(f"person.profiles[{index}] doit contenir network et url")
        elif not re.fullmatch(r"https://[^\s]+", text(profile_item["url"])):
            errors.append(f"person.profiles[{index}].url doit être une URL HTTPS absolue")

    if not re.fullmatch(r"https://[^\s]+/", text(data.get("meta", {}).get("canonical_url"))):
        errors.append("meta.canonical_url doit être une URL HTTPS absolue terminée par /")
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.pdf", text(data.get("meta", {}).get("pdf_filename"))):
        errors.append("meta.pdf_filename doit être un nom de fichier PDF relatif sans dossier")
    if not isinstance(data.get("meta", {}).get("pdf_pages"), int) or data["meta"]["pdf_pages"] < 1:
        errors.append("meta.pdf_pages doit être un entier positif")
    if not re.fullmatch(r"G-[A-Z0-9]+", text(data.get("meta", {}).get("analytics_id"))):
        errors.append("meta.analytics_id doit être un identifiant Google Analytics de type G-XXXXXXXXXX")
    if not data.get("meta", {}).get("description"):
        errors.append("meta.description est obligatoire")
    else:
        try:
            data["meta"]["description"].format(name="Prénom Nom", experience_years=1)
        except (KeyError, ValueError) as exc:
            errors.append(f"meta.description contient un placeholder invalide : {exc}")
    allowed_themes = {"blue", "green", "red", "purple", "amber", "grey"}
    if data.get("meta", {}).get("theme") not in allowed_themes:
        errors.append("meta.theme inconnu (voir la liste des thèmes dans le README)")
    if "{experience_years}" not in text(data.get("profile", {}).get("summary")):
        errors.append("profile.summary doit contenir {experience_years} pour rester à jour")
    for field in ("objective_title", "objective_label"):
        if not data.get("profile", {}).get(field):
            errors.append(f"champ obligatoire absent : profile.{field}")

    for index, item in enumerate(data.get("experiences", []), start=1):
        for field in ("company", "position", "location", "start", "end"):
            if not item.get(field):
                errors.append(f"experiences[{index}].{field} est obligatoire")
        if not item.get("summary") and not item.get("highlights"):
            errors.append(f"experiences[{index}] doit contenir summary ou highlights")

    for section, fields in {
        "skills": ("name", "keywords"), "certifications": ("name", "date", "url"),
        "education": ("degree", "institution", "end"), "languages": ("language", "level"),
        "interests": ("name", "details"),
    }.items():
        for index, item in enumerate(data.get(section, []), start=1):
            for field in fields:
                if not item.get(field):
                    errors.append(f"{section}[{index}].{field} est obligatoire")

    for index, item in enumerate(data.get("skills", []), start=1):
        keywords = item.get("keywords")
        if not isinstance(keywords, list) or not all(isinstance(keyword, str) and keyword.strip() for keyword in keywords):
            errors.append(f"skills[{index}].keywords doit être une liste YAML de textes non vides")

    if errors:
        raise SystemExit("cv.yml invalide :\n- " + "\n- ".join(errors))


def text(value: object) -> str:
    return "" if value is None else str(value)


def h(value: object) -> str:
    return escape(text(value), quote=True)


def age_on(birth_date: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def experience_years(data: dict) -> int:
    return date.today().year - int(data["profile"]["experience_since"])


def profile_summary(data: dict) -> str:
    return data["profile"]["summary"].format(experience_years=experience_years(data))


def availability_values(person: dict) -> tuple[str, str]:
    return text(person.get("availability")).strip(), iso_date(person.get("availability_period")).strip()


def phone_is_public(person: dict) -> bool:
    return bool(person.get("phone_uri")) and not person.get("phone_pdf_only", False)


def skill_keywords(item: dict) -> list[str]:
    """Retourne les compétences atomiques définies dans cv.yml."""
    return [keyword.strip() for keyword in item["keywords"]]


def iso_date(value: object) -> str:
    return value.isoformat() if isinstance(value, date) else text(value)


def display_date(value: object, *, start: bool = False) -> str:
    value = iso_date(value)
    if value == "present":
        return "aujourd’hui"
    if re.fullmatch(r"\d{4}-\d{2}", value):
        month = MONTHS[value[-2:]]
        label = f"{month} {value[:4]}"
        return label.capitalize() if start else label
    return value


def period(item: dict) -> str:
    start = iso_date(item.get("start"))
    end = iso_date(item.get("end"))
    start_html = f'<time datetime="{h(start)}">{h(display_date(start, start=True))}</time>' if start else ""
    if not end or end == start:
        return start_html
    end_html = h(display_date(end)) if end == "present" else f'<time datetime="{h(end)}">{h(display_date(end))}</time>'
    return f"{start_html} – {end_html}"


def company_line(item: dict) -> str:
    parts = [item.get("company"), item.get("type"), item.get("location")]
    if item.get("client"):
        parts.append(f"Client {item['client']}")
    return " · ".join(h(part) for part in parts if part)


def job_html(item: dict) -> str:
    classes = "job compact" if item.get("compact") else "job"
    body: list[str] = []
    if item.get("highlights"):
        highlights = "\n".join(f"    <li>{h(point)}</li>" for point in item["highlights"])
        body.append(f"  <ul>\n{highlights}\n  </ul>")
    if item.get("summary"):
        body.append(f"  <p>{h(item['summary'])}</p>")
    if item.get("clients"):
        body.append(f'  <p class="clients"><strong>Clients :</strong> {h(item["clients"])}</p>')
    content = "\n".join(body)
    return f'''<article class="{classes}">
  <header>
    <div>
      <h3>{h(item["position"])}</h3>
      <p class="company">{company_line(item)}</p>
    </div>
    <p class="date">{period(item)}</p>
  </header>
{content}
</article>'''


def build_head(data: dict) -> str:
    person, profile = data["person"], data["profile"]
    name = f'{person["first_name"]} {person["last_name"]}'
    description = data["meta"]["description"].format(name=name, experience_years=experience_years(data))
    canonical_url = data["meta"]["canonical_url"]
    person_entity = {
        "@type": "Person",
        "@id": f"{canonical_url}#person",
        "name": name,
        "givenName": person["first_name"],
        "familyName": person["last_name"],
        "url": canonical_url,
        "jobTitle": person["professional_title"],
        "hasOccupation": {
            "@type": "Occupation",
            "name": person["title"],
        },
        "email": f'mailto:{person["email"]}',
        "address": {
            "@type": "PostalAddress", "addressLocality": person["location"],
            "addressRegion": person["region"], "postalCode": person["postal_code"],
            "addressCountry": person["country_code"],
        },
        "sameAs": [item["url"] for item in person["profiles"]],
        "knowsLanguage": [
            {"@type": "Language", "name": item["language"]} for item in data["languages"]
        ],
        "knowsAbout": profile["specialties"] + [item["name"] for item in data["skills"]],
    }
    if person.get("show_age", True):
        person_entity["birthDate"] = iso_date(person["birth_date"])
    if phone_is_public(person):
        person_entity["telephone"] = person["phone_uri"]
    title = f'{name} — {person["title"]}'
    json_ld = {
        "@context": "https://schema.org",
        "@type": "ProfilePage",
        "@id": f"{canonical_url}#profile",
        "url": canonical_url,
        "name": title,
        "dateModified": profile_modified_datetime(),
        "mainEntity": person_entity,
    }
    analytics_id = h(data["meta"]["analytics_id"])
    critical_css = indent((ROOT / "styles-critical.css").read_text(encoding="utf-8").strip(), "    ")
    return f'''  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{h(title)}</title>
  <meta name="description" content="{h(description)}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <script>
    try {{
      const defaultColor = document.documentElement.dataset.theme;
      const savedColor = localStorage.getItem("cv-color");
      const color = /^(?:blue|green|red|purple|amber|grey)$/.test(savedColor) ? savedColor : defaultColor;
      const savedMode = localStorage.getItem("cv-mode");
      const dark = savedMode ? savedMode === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
      document.documentElement.dataset.theme = dark ? `dark_${{color}}` : color;
    }} catch {{ /* Le thème par défaut reste actif si le stockage est indisponible. */ }}
  </script>
  <link rel="canonical" href="{h(canonical_url)}">
  <link rel="alternate" type="application/json" href="resume.json" title="CV structuré JSON">
  <!--
    CSS critique intégré depuis styles-critical.css pendant la génération.
    Il met en forme immédiatement le premier écran sans attendre styles.css,
    qui est préchargé puis appliqué sans bloquer le rendu de la page.
  -->
  <style>
{critical_css}
  </style>
  <link rel="preload" href="styles.css" as="style">
  <link rel="stylesheet" href="styles.css" media="print" data-deferred-styles>
  <script>
    const deferredStyles = document.querySelector("[data-deferred-styles]");
    deferredStyles.addEventListener("load", () => {{ deferredStyles.media = "all"; }});
  </script>
  <noscript><link rel="stylesheet" href="styles.css"></noscript>
  <script src="profile.js" defer></script>
  <script src="contact.js" defer></script>
  <script src="theme.js" defer></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag() {{ dataLayer.push(arguments); }}
    function loadAnalytics() {{
      const script = document.createElement("script");
      script.src = "https://www.googletagmanager.com/gtag/js?id={analytics_id}";
      script.async = true;
      document.head.append(script);
      gtag("js", new Date());
      gtag("config", "{analytics_id}");
    }}
    if (location.protocol === "http:" || location.protocol === "https:") {{
      addEventListener("load", () => {{
        if ("requestIdleCallback" in window) requestIdleCallback(loadAnalytics, {{ timeout: 2000 }});
        else setTimeout(loadAnalytics, 1000);
      }}, {{ once: true }});
    }}
  </script>
  <meta property="og:type" content="profile">
  <meta property="og:title" content="{h(title)}">
  <meta property="og:description" content="{h(description)}">
  <meta property="og:url" content="{h(canonical_url)}">
  <meta property="og:image" content="{h(urljoin(canonical_url, person['photo']))}">
  <script type="application/ld+json">
{json.dumps(json_ld, ensure_ascii=False, indent=2)}
  </script>'''


def build_header(data: dict) -> str:
    person, profile = data["person"], data["profile"]
    name = f'{person["first_name"]} {person["last_name"]}'
    birth = person["birth_date"]
    current_age = age_on(birth)
    age_html = f'<time datetime="{birth.isoformat()}" data-age>{current_age} ans</time>'
    personal_details = " · ".join(
        item for item in (age_html if person.get("show_age", True) else "", h(person["driving_licence"])) if item
    )
    availability, availability_period = availability_values(person)
    availability_parts = []
    if availability:
        availability_parts.append(f"<strong>{h(availability)}</strong>")
    if availability_period:
        availability_parts.append(f'<span class="availability-period">(Disponibilité : {h(availability_period)})</span>')
    availability_class = {
        "En recherche active": "active",
        "Ouvert aux opportunités": "open",
        "Non disponible actuellement": "unavailable",
    }.get(availability, "unspecified")
    availability_html = ""
    if availability_parts:
        availability_html = f'        <p class="availability {availability_class}"><span class="availability-dot" aria-hidden="true"></span><span class="availability-copy">{"".join(availability_parts)}</span></p>\n'
    print_availability = ""
    if availability:
        print_availability += f'              <div class="print-availability-start"><dt>Statut</dt><dd>{h(availability)}</dd></div>\n'
    if availability_period:
        availability_class = "" if availability else ' class="print-availability-start"'
        print_availability += f'              <div{availability_class}><dt>Disponibilité</dt><dd>{h(availability_period)}</dd></div>\n'
    print_phone = ""
    if person.get("phone_uri"):
        print_phone = f'              <div><dt>Téléphone</dt><dd><a href="tel:{h(person["phone_uri"])}">{h(person["phone_display"])}</a></dd></div>\n'
    show_qr_code = person.get("show_qr_code", False)
    print_contact_class = "print-contact" if show_qr_code else "print-contact without-qr"
    print_qr = ""
    if show_qr_code:
        print_qr = f'''          <div class="print-qr"><img src="assets/cv-qr.svg" alt="QR code vCard de {h(name)}" width="99" height="99"><span>Ajouter le contact</span></div>\n'''
    photo_path = Path(person["photo"])
    photo_base = str(photo_path.with_suffix(""))
    photo_sizes = "(max-width: 560px) 110px, (max-width: 850px) 120px, 180px"
    if photo_path.suffix.lower() == ".svg":
        portrait = f'''      <div class="portrait-wrap">
        <img class="portrait" src="{h(photo_path)}" alt="Portrait de {h(name)}" width="180" height="180" fetchpriority="high">
      </div>'''
    else:
        portrait = f'''      <picture class="portrait-wrap">
        <source type="image/avif" srcset="{h(photo_base)}-180.avif 180w, {h(photo_base)}-360.avif 360w" sizes="{photo_sizes}">
        <source type="image/webp" srcset="{h(photo_base)}-180.webp 180w, {h(photo_base)}-360.webp 360w" sizes="{photo_sizes}">
        <img class="portrait" src="{h(photo_base)}-360.jpg" srcset="{h(photo_base)}-180.jpg 180w, {h(photo_base)}-360.jpg 360w" sizes="{photo_sizes}" alt="Portrait de {h(name)}" width="180" height="180" fetchpriority="high">
      </picture>'''
    profiles = "\n".join(
        f'          <a href="{h(item["url"])}"><img src="assets/brands/{h(item["network"].lower())}.svg" alt="" aria-hidden="true" width="16" height="16">{h(item["network"])}</a>'
        for item in person["profiles"]
    )
    tags = "\n".join(f"          <li>{h(tag)}</li>" for tag in profile["tags"])
    return f'''  <header class="hero">
    <div class="hero-inner">
{portrait}
      <div>
        <p class="eyebrow">{h(person['eyebrow'])} · {h(person['location'])}</p>
        <h1>{h(name)}</h1>
        <p class="role">{h(person['title'])}</p>
        <ul class="pill-list" aria-label="Expertises principales">
{tags}
        </ul>
      </div>
      <div class="contact-card" aria-label="Coordonnées et profils">
{availability_html}        <p>{personal_details}</p>
        <p>{h(person['location'])} ({h(person['postal_code'])})</p>
        <p class="profile-links">
{profiles}
        </p>
        <p><button class="contact-opener" type="button" data-open-contact>Me contacter</button></p>
        <a class="print-button" href="{h(data['meta']['pdf_filename'])}" download>
          <span>Télécharger</span>
          <span>au format PDF</span>
        </a>
        <div class="{print_contact_class}" aria-label="Coordonnées pour la version imprimée">
          <div class="print-contact-details">
            <p class="print-contact-title"><strong>Coordonnées</strong></p>
            <div class="print-contact-personal">
              <p>{h(person['location'])} ({h(person['postal_code'])}), {h(person['country'])}</p>
              <p>{personal_details}</p>
            </div>
            <dl class="print-contact-links">
              <div><dt>E-mail</dt><dd><a href="mailto:{h(person['email'])}">{h(person['email'])}</a></dd></div>
{print_phone}              <div><dt>CV en ligne</dt><dd><a href="{h(data['meta']['canonical_url'])}">{h(data['meta']['canonical_url'].removeprefix('https://').rstrip('/'))}</a></dd></div>
{print_availability}
            </dl>
          </div>
{print_qr}        </div>
      </div>
    </div>
  </header>'''


def build_main(data: dict) -> str:
    profile = data["profile"]
    recent = [item for item in data["experiences"] if not item.get("compact")]
    earlier = [item for item in data["experiences"] if item.get("compact")]
    specialties = " · ".join(h(item) for item in profile["specialties"])
    jobs = "\n".join(indent(job_html(item), "        ") for item in recent)
    earlier_jobs = "\n".join(indent(job_html(item), "          ") for item in earlier)
    skills = "\n".join(
        f'          <div>\n            <dt>{h(item["name"])}</dt>\n            <dd>{h(", ".join(skill_keywords(item)))}</dd>\n          </div>'
        for item in data["skills"]
    )
    certs = "\n".join(
        f'''        <article class="credential">
          <h3>{h(item["name"])}</h3>
          <p><time datetime="{h(item["date"])}">{h(item["date"])}</time> · <a href="{h(item["url"])}">Vérifier sur Credly</a></p>
        </article>''' for item in data["certifications"]
    )
    education = "\n".join(
        f'        <h3>{h(item["degree"])}</h3>\n        <p>{h(item["institution"])} · {education_period(item)}</p>'
        for item in data["education"]
    )
    languages = "\n".join(
        f'          <li><strong>{h(item["language"])} :</strong> {h(item["level"])}</li>' for item in data["languages"]
    )
    interests = "\n".join(
        f'        <p><strong>{h(item["name"])} :</strong> {h(item["details"])}</p>' for item in data["interests"]
    )
    start_year = min(int(iso_date(item["start"])[:4]) for item in earlier)
    end_year = max(int(iso_date(item["end"])[:4]) for item in earlier)
    return f'''  <main id="contenu" class="layout">
    <div>
      <section id="profil" aria-labelledby="titre-profil">
        <h2 id="titre-profil">Profil professionnel</h2>
        <p class="lead">{h(profile_summary(data))}</p>
        <p class="specialties"><strong>Spécialités :</strong> {specialties}</p>
        <p>{h(profile['approach'])}</p>
        <p>{h(profile['clearance'])}</p>
      </section>
      <section id="experience" aria-labelledby="titre-experience">
        <h2 id="titre-experience">Expérience professionnelle</h2>
{jobs}
        <details class="earlier">
          <summary>Expériences antérieures ({start_year}–{end_year})</summary>
{earlier_jobs}
        </details>
      </section>
    </div>
    <aside class="side-column" aria-label="Compétences et qualifications">
      <section id="competences" aria-labelledby="titre-competences">
        <h2 id="titre-competences">Compétences techniques</h2>
        <dl class="skills">
{skills}
        </dl>
      </section>
      <section id="certifications" aria-labelledby="titre-certifications">
        <h2 id="titre-certifications">Certifications &amp; formation continue</h2>
{certs}
      </section>
      <section id="formation" aria-labelledby="titre-formation">
        <h2 id="titre-formation">Formation</h2>
{education}
      </section>
      <section aria-labelledby="titre-langues">
        <h2 id="titre-langues">Langues</h2>
        <ul class="plain">
{languages}
        </ul>
      </section>
      <section aria-labelledby="titre-interets">
        <h2 id="titre-interets">Centres d’intérêt</h2>
{interests}
      </section>
    </aside>
  </main>'''


def education_period(item: dict) -> str:
    start, end = iso_date(item.get("start")), iso_date(item.get("end"))
    if start and end and start != end:
        return f'<time datetime="{h(start)}">{h(start)}</time>–<time datetime="{h(end)}">{h(end)}</time>'
    value = end or start
    return f'<time datetime="{h(value)}">{h(value)}</time>'


def build_dialog(data: dict) -> str:
    person = data["person"]
    phone = ""
    if phone_is_public(person):
        phone = f'      <a class="contact-item" href="tel:{h(person["phone_uri"])}"><span aria-hidden="true">☎</span><span><strong>Téléphone</strong>{h(person["phone_display"])}</span></a>\n'
    return f'''  <dialog class="contact-dialog" id="contact-dialog" aria-labelledby="contact-dialog-title">
    <div class="dialog-header">
      <h2 id="contact-dialog-title">Mes coordonnées</h2>
      <button class="dialog-close" type="button" data-close-contact aria-label="Fermer la fenêtre de contact">×</button>
    </div>
    <div class="dialog-body">
      <a class="contact-item" href="mailto:{h(person['email'])}"><span aria-hidden="true">@</span><span><strong>E-mail</strong>{h(person['email'])}</span></a>
{phone}      <a class="contact-item" href="{h(person['appointment_url'])}" target="_blank" rel="noopener noreferrer"><span aria-hidden="true">▣</span><span><strong>Prise de rendez-vous</strong>{h(person['appointment_description'])}</span></a>
    </div>
  </dialog>'''


def replace_region(template: str, name: str, content: str) -> str:
    pattern = rf"(?s)(\s*<!-- GENERATED:{name}:START -->).*?(<!-- GENERATED:{name}:END -->)"
    replacement = rf"\1\n{content}\n  \2"
    result, count = re.subn(pattern, replacement, template)
    if count != 1:
        raise ValueError(f"Région de template introuvable ou dupliquée : {name}")
    return result


def build_html(data: dict, template: str) -> str:
    output = re.sub(
        r'<html lang="[^"]+" data-theme="[^"]+">',
        f'<html lang="{h(data["meta"]["language"])}" data-theme="{h(data["meta"]["theme"])}">',
        template,
        count=1,
    )
    output = replace_region(output, "HEAD", build_head(data))
    output = replace_region(output, "HEADER", build_header(data))
    output = replace_region(output, "MAIN", build_main(data))
    output = replace_region(output, "DIALOG", build_dialog(data))
    generated_on = date.today()
    footer = f'''  <footer>
    <p>Dernière mise à jour : {generated_on.day} {MONTHS[f'{generated_on.month:02d}']} {generated_on.year} · <a href="resume.json">Version JSON</a> · <a href="llms.txt">Version texte pour agents IA</a></p>
  </footer>'''
    return replace_region(output, "FOOTER", footer).rstrip() + "\n"


def build_resume(data: dict) -> dict:
    person, profile = data["person"], data["profile"]
    complete_summary = " ".join((profile_summary(data), profile["approach"], profile["clearance"]))
    basics = {
        "name": f'{person["first_name"]} {person["last_name"]}',
        "label": person["professional_title"], "image": person["photo"],
        "email": person["email"],
        "url": data["meta"]["canonical_url"], "summary": complete_summary,
        "location": {"postalCode": person["postal_code"], "city": person["location"], "region": person["region"], "countryCode": person["country_code"]},
        "profiles": person["profiles"],
    }
    if phone_is_public(person):
        basics["phone"] = person["phone_display"]
    availability, availability_period = availability_values(person)
    if availability or availability_period:
        basics["availability"] = {
            key: value for key, value in (("status", availability), ("period", availability_period)) if value
        }
    return {
        "$schema": "https://raw.githubusercontent.com/jsonresume/resume-schema/master/schema.json",
        "basics": basics,
        "work": [resume_work(item) for item in data["experiences"]],
        "education": [{"institution": item["institution"], "area": item["degree"], "startDate": iso_date(item.get("start")), "endDate": iso_date(item.get("end"))} for item in data["education"]],
        "certificates": [{"name": item["name"], "date": iso_date(item["date"]), "issuer": item["issuer"], "url": item["url"]} for item in data["certifications"]],
        "skills": [{"name": item["name"], "keywords": skill_keywords(item)} for item in data["skills"]],
        "languages": [{"language": item["language"], "fluency": item["level"]} for item in data["languages"]],
        "interests": [{"name": item["name"], "keywords": [item["details"]]} for item in data["interests"]],
    }


def resume_work(item: dict) -> dict:
    result = {"name": item["company"], "position": item["position"], "location": item["location"], "startDate": iso_date(item.get("start")), "endDate": "" if item.get("end") == "present" else iso_date(item.get("end"))}
    if item.get("summary"):
        result["summary"] = item["summary"]
    if item.get("highlights"):
        result["highlights"] = item["highlights"]
    if item.get("clients"):
        result.setdefault("highlights", []).append(f'Clients : {item["clients"]}')
    return result


def build_llms(data: dict) -> str:
    person, profile = data["person"], data["profile"]
    lines = [
        f'# {person["first_name"]} {person["last_name"]} — CV', "",
        f'> {person["professional_title"]}, basé à {person["location"]}. Plus de {experience_years(data)} ans d’expérience.', "",
        f'## {profile["objective_title"]}', f'{profile["objective_label"]} : ' + ", ".join(profile["specialties"]) + ".", "",
        "## Compétences clés",
    ]
    lines.extend(f'- {item["name"]} : {", ".join(skill_keywords(item))}' for item in data["skills"])
    lines += ["", profile["approach"], profile["clearance"], "", "## Expérience"]
    for item in data["experiences"]:
        lines.append(f'- {period_plain(item)} : {item["position"]}, {item["company"]}, {item["location"]}.')
        if item.get("summary"):
            lines.append(f'  - {item["summary"]}')
        lines.extend(f'  - {point}' for point in item.get("highlights", []))
        if item.get("clients"):
            lines.append(f'  - Clients : {item["clients"]}')
    lines += ["", "## Certifications & formation continue"]
    lines.extend(f'- [{item["name"]}]({item["url"]}), {item["date"]}' for item in data["certifications"])
    lines += ["", "## Formation"]
    lines.extend(f'- {item["degree"]}, {item["institution"]}, {period_plain({"start": item.get("start"), "end": item.get("end")})}' for item in data["education"])
    lines += ["", "## Langues"]
    lines.extend(f'- {item["language"]} : {item["level"]}' for item in data["languages"])
    lines += ["", "## Centres d’intérêt"]
    lines.extend(f'- {item["name"]} : {item["details"]}' for item in data["interests"])
    lines += ["", "## Contact"]
    availability, availability_period = availability_values(person)
    if availability:
        lines.append(f"- Statut : {availability}")
    if availability_period:
        lines.append(f"- Disponibilité : {availability_period}")
    lines.append(f'- E-mail : {person["email"]}')
    if phone_is_public(person):
        lines.append(f'- Téléphone : {person["phone_display"]}')
    lines.append(f'- [Prendre rendez-vous]({person["appointment_url"]})')
    lines.extend(f'- [{item["network"]}]({item["url"]})' for item in person["profiles"])
    lines += [f'- [CV HTML]({data["meta"]["canonical_url"]})', f'- [Données JSON]({data["meta"]["canonical_url"].rstrip("/")}/resume.json)', ""]
    return "\n".join(lines)


def build_date() -> str:
    """Retourne la date du build, stable pendant toute la journée."""
    return date.today().isoformat()


def profile_modified_datetime() -> str:
    """Google ProfilePage attend un DateTime ISO 8601 avec fuseau horaire."""
    return f"{build_date()}T00:00:00+00:00"


def build_sitemap(data: dict) -> str:
    canonical_url = h(data["meta"]["canonical_url"])
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{canonical_url}</loc>
    <lastmod>{build_date()}</lastmod>
  </url>
</urlset>
'''


def build_robots(data: dict) -> str:
    sitemap_url = urljoin(data["meta"]["canonical_url"], "sitemap.xml")
    return f'''# Autorise l'indexation dans ChatGPT Search sans autoriser l'entraînement.
User-agent: OAI-SearchBot
Allow: /

User-agent: GPTBot
Disallow: /

User-agent: *
Allow: /

Sitemap: {sitemap_url}
'''


def period_plain(item: dict) -> str:
    start, end = display_date(item.get("start"), start=True), display_date(item.get("end"))
    if not start:
        return end
    return start if not end or start.lower() == end else f"{start}–{end}"


def build_vcard(data: dict) -> str:
    person = data["person"]
    fields = [
        "BEGIN:VCARD", "VERSION:3.0",
        f'N:{person["last_name"]};{person["first_name"]};;;',
        f'FN:{person["first_name"]} {person["last_name"]}',
        f'TITLE:{person["title"]}',
        f'EMAIL;TYPE=INTERNET:{person["email"]}', f'URL:{data["meta"]["canonical_url"]}',
        f'ADR;TYPE=WORK:;;{person["location"]};{person["region"]};{person["postal_code"]};{person["country"]}',
        "END:VCARD",
    ]
    if person.get("phone_uri"):
        fields.insert(5, f'TEL;TYPE=CELL:{person["phone_uri"]}')
    return "\r\n".join(fields)


def write_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")
    print(f"generated {path.relative_to(ROOT)}")


def render_qr(vcard: str) -> str:
    executable = shutil.which("qrencode")
    if not executable:
        raise SystemExit("qrencode est requis pour générer assets/cv-qr.svg")
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        subprocess.run([executable, "-t", "SVG", "-l", "M", "-m", "2", "-o", str(temporary), vcard], check=True)
        return temporary.read_text(encoding="utf-8")
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="échoue si les fichiers générés ne sont pas à jour")
    parser.add_argument("--print-pdf-filename", action="store_true", help="affiche le nom du PDF configuré")
    args = parser.parse_args()
    data = yaml.safe_load((ROOT / "cv.yml").read_text(encoding="utf-8"))
    validate_data(data)
    if args.print_pdf_filename:
        print(data["meta"]["pdf_filename"])
        return
    template = (ROOT / "templates/index.html").read_text(encoding="utf-8")
    qr_path = ROOT / "assets/cv-qr.svg"
    generated = {
        ROOT / "index.html": build_html(data, template),
        ROOT / "resume.json": json.dumps(build_resume(data), ensure_ascii=False, indent=2) + "\n",
        ROOT / "llms.txt": build_llms(data),
        ROOT / "robots.txt": build_robots(data),
        ROOT / "sitemap.xml": build_sitemap(data),
    }
    if data["person"].get("show_qr_code", False):
        generated[qr_path] = render_qr(build_vcard(data))
    if args.check:
        stale = [path.relative_to(ROOT) for path, content in generated.items() if not path.exists() or path.read_text(encoding="utf-8") != content]
        if not data["person"].get("show_qr_code", False) and qr_path.exists():
            stale.append(qr_path.relative_to(ROOT))
        if stale:
            raise SystemExit("Fichiers générés obsolètes : " + ", ".join(map(str, stale)))
        print("Fichiers générés synchronisés : OK")
        return
    for path, content in generated.items():
        write_if_changed(path, content)
    if not data["person"].get("show_qr_code", False) and qr_path.exists():
        qr_path.unlink()
        print(f"removed {qr_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
