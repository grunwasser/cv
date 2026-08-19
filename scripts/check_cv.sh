#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
python_bin=${PYTHON_BIN:-python3}
cd "$project_dir"

"$python_bin" scripts/build_cv.py --check

"$python_bin" - <<'PY'
from datetime import date
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import yaml

from scripts.build_cv import build_vcard

class Audit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.duplicate_ids = []
        self.local_refs = []
        self.anchor_refs = []
        self.headings = []
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        element_id = attrs.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.append(element_id)
            self.ids.add(element_id)
        if tag in {"a", "link", "script", "img"}:
            ref = attrs.get("href") or attrs.get("src")
            if ref and not ref.startswith(("http:", "https:", "mailto:", "tel:", "#", "data:")):
                self.local_refs.append(ref.split("?", 1)[0])
            if ref and ref.startswith("#"):
                self.anchor_refs.append(ref[1:])
        if tag == "img":
            self.images.append(attrs)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings.append(int(tag[1]))

html = Path("index.html").read_text(encoding="utf-8")
htaccess = Path(".htaccess").read_text(encoding="utf-8")
source = yaml.safe_load(Path("cv.yml").read_text(encoding="utf-8"))
build_date = date.today().isoformat()
resume = json.loads(Path("resume.json").read_text(encoding="utf-8"))
llms = Path("llms.txt").read_text(encoding="utf-8")
robots = Path("robots.txt").read_text(encoding="utf-8")
sitemap = ET.parse("sitemap.xml").getroot()
audit = Audit()
audit.feed(html)
json_ld_match = re.search(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', html, re.DOTALL)
assert json_ld_match, "Données JSON-LD absentes"
json_ld = json.loads(json_ld_match.group(1))
person_ld = json_ld.get("mainEntity", {})

implementation_paths = [Path("Makefile"), *Path("scripts").glob("*"), *Path("templates").glob("*")]
implementation = "\n".join(
    path.read_text(encoding="utf-8") for path in implementation_paths if path.is_file()
)
personal_literals = filter(None, (
    source["person"]["first_name"], source["person"]["last_name"], source["person"]["email"],
    source["person"]["birth_date"].isoformat(), source["person"]["photo"],
    source["meta"]["canonical_url"], source["meta"]["pdf_filename"],
))
assert not [value for value in personal_literals if value in implementation], "Valeur personnelle codée en dur dans les scripts"

assert not audit.duplicate_ids, f"IDs dupliqués : {audit.duplicate_ids}"
for directive in ("Options -Indexes", "Content-Security-Policy", "X-Content-Type-Options", "Cache-Control", "X-Robots-Tag"):
    assert directive in htaccess, f"Directive de sécurité Apache absente : {directive}"
assert source["meta"]["pdf_filename"] not in htaccess, "Le nom du PDF ne doit pas être codé en dur dans .htaccess"
assert audit.headings.count(1) == 1, "Le document doit contenir un seul H1"
assert all(current - previous <= 1 for previous, current in zip(audit.headings, audit.headings[1:])), "Saut dans la hiérarchie des titres"
assert all(ref in audit.ids for ref in audit.anchor_refs), "Ancre interne manquante"
missing_refs = [ref for ref in audit.local_refs if not Path(ref).exists() and ref != source["meta"]["pdf_filename"]]
assert not missing_refs, f"Ressource locale manquante : {missing_refs}"
assert all("alt" in image for image in audit.images), "Chaque image doit déclarer un attribut alt"
assert "/cv/contacts" not in html and "/var/users/" not in html, "Dépendance détectée vers l'ancien CV"
expected_experience = date.today().year - int(source["profile"]["experience_since"])
assert f"plus de {expected_experience} ans" in html.lower(), "Accroche d'expérience absente ou obsolète"
canonical_url = source["meta"]["canonical_url"]
assert f'rel="canonical" href="{canonical_url}"' in html, "URL canonique absolue absente"
assert f'property="og:url" content="{canonical_url}"' in html, "URL Open Graph incohérente"
assert json_ld.get("@type") == "ProfilePage", "Le JSON-LD doit décrire une ProfilePage"
assert json_ld.get("url") == canonical_url, "URL ProfilePage incohérente"
assert json_ld.get("dateModified") == f'{build_date}T00:00:00+00:00', "DateTime ProfilePage incohérent"
assert person_ld.get("@type") == "Person", "Entité Person absente de la ProfilePage"
assert person_ld.get("@id") == f"{canonical_url}#person", "Identifiant de la Person incohérent"
assert person_ld.get("hasOccupation", {}).get("name") == source["person"]["title"], "Métier JSON-LD incohérent"
namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
assert sitemap.tag == f'{{{namespace["sm"]}}}urlset', "Racine sitemap.xml invalide"
assert sitemap.findtext("sm:url/sm:loc", namespaces=namespace) == canonical_url, "URL du sitemap incohérente"
assert sitemap.findtext("sm:url/sm:lastmod", namespaces=namespace) == build_date, "Date du sitemap incohérente"
if Path("cv.en.yml").exists():
    source_en = yaml.safe_load(Path("cv.en.yml").read_text(encoding="utf-8"))
    html_en = Path("en/index.html").read_text(encoding="utf-8")
    canonical_en = source_en["meta"]["canonical_url"]
    sitemap_urls = {node.text for node in sitemap.findall("sm:url/sm:loc", namespace)}
    assert sitemap_urls == {canonical_url, canonical_en}, "Versions linguistiques incomplètes dans le sitemap"
    assert '<html lang="en"' in html_en, "Langue anglaise absente du HTML"
    assert f'hreflang="fr" href="{canonical_url}"' in html_en, "Retour hreflang français absent"
    assert f'hreflang="en" href="{canonical_en}"' in html, "Hreflang anglais absent"
    assert 'href="../" lang="fr" hreflang="fr"' in html_en, "Switch EN vers FR absent"
    assert 'href="en/" lang="en" hreflang="en"' in html, "Switch FR vers EN absent"
assert "User-agent: OAI-SearchBot\nAllow: /" in robots, "OAI-SearchBot doit être autorisé"
assert "User-agent: GPTBot\nDisallow: /" in robots, "GPTBot doit être bloqué"
assert f"Sitemap: {canonical_url}sitemap.xml" in robots, "Sitemap absent de robots.txt"
assert "?v=" not in html, "Paramètre de version inutile détecté dans les ressources"
assert '<link rel="preload" href="styles.css" as="style">' in html, "Préchargement CSS absent"
assert 'data-deferred-styles' in html, "Chargement CSS différé absent"
critical_css = Path("styles-critical.css").read_text(encoding="utf-8").strip()
assert all(line in html for line in critical_css.splitlines()), "CSS critique non synchronisé"
analytics_id = source["meta"]["analytics_id"]
assert html.count(analytics_id) == 2, "Balise Google Analytics absente ou dupliquée"
photo_base = Path(source["person"]["photo"]).with_suffix("")
if Path(source["person"]["photo"]).suffix.lower() != ".svg":
    for size in (180, 360):
        for extension in ("avif", "webp", "jpg"):
            assert photo_base.with_name(f"{photo_base.name}-{size}.{extension}").exists(), "Variante responsive du portrait absente"
birth_date = source["person"]["birth_date"].isoformat()
if source["person"].get("show_age", True):
    assert html.count(f'datetime="{birth_date}" data-age') == 2, "Date de naissance non centralisée dans les affichages de l'âge"
    assert person_ld.get("birthDate") == birth_date, "Date de naissance absente des données structurées"
else:
    assert birth_date not in html and "birthDate" not in person_ld, "Date de naissance présente alors que l'âge est masqué"
assert '<details class="earlier">' in html, "Les expériences antérieures doivent être repliées par défaut"
assert html.count('<article class="job') == len(source["experiences"]), "Expériences HTML incomplètes"
assert len(resume["work"]) == len(source["experiences"]), "Expériences JSON incomplètes"
assert source["person"]["email"] in html and source["person"]["email"] in llms, "E-mail désynchronisé"
phone_display = source["person"].get("phone_display")
if phone_display:
    assert phone_display in html, "Téléphone absent des coordonnées PDF"
    if source["person"].get("phone_pdf_only", False):
        assert phone_display not in llms, "Téléphone PDF présent dans llms.txt"
        assert "phone" not in resume["basics"] and "telephone" not in person_ld, "Téléphone PDF présent dans les données structurées"
        assert 'class="contact-item" href="tel:' not in html, "Téléphone PDF présent dans la fenêtre de contact web"
    else:
        assert phone_display in llms, "Téléphone public absent de llms.txt"
        assert resume["basics"].get("phone") == phone_display, "Téléphone public absent du JSON"
        assert person_ld.get("telephone") == source["person"]["phone_uri"], "Téléphone public absent du JSON-LD"
else:
    assert "Téléphone" not in html and "Téléphone" not in llms, "Téléphone présent alors qu'il est désactivé"
    assert "phone" not in resume["basics"] and "telephone" not in person_ld, "Téléphone présent dans les données structurées"
availability = str(source["person"].get("availability") or "")
availability_period = str(source["person"].get("availability_period") or "")
if availability or availability_period:
    assert all(value in html and value in llms for value in (availability, availability_period) if value), "Disponibilité désynchronisée"
    assert "availability" in resume["basics"], "Disponibilité absente du JSON"
else:
    assert '<p class="availability ' not in html, "Disponibilité affichée alors qu'elle est vide"
    assert "availability" not in resume["basics"], "Disponibilité vide présente dans le JSON"
qr_path = Path("assets/cv-qr.svg")
if source["person"].get("show_qr_code", False):
    assert qr_path.exists() and "assets/cv-qr.svg" in html, "QR code activé mais absent"
    if source["person"].get("phone_uri"):
        assert f'TEL;TYPE=CELL:{source["person"]["phone_uri"]}' in build_vcard(source), "Téléphone absent de la vCard"
else:
    assert not qr_path.exists() and "assets/cv-qr.svg" not in html, "QR code présent alors qu'il est désactivé"
print("Structure HTML et ressources : OK")
PY

set +e
browser_args=()
if [[ -n ${PDF_OUTPUT:-} ]]; then
  browser_args+=(--pdf-output "$PDF_OUTPUT")
fi
"$python_bin" scripts/browser_checks.py "${browser_args[@]}"
browser_status=$?
if [[ $browser_status -eq 0 && -f cv.en.yml ]]; then
  browser_args_en=(--source cv.en.yml --html en/index.html)
  if [[ -n ${PDF_OUTPUT_EN:-} ]]; then
    browser_args_en+=(--pdf-output "$PDF_OUTPUT_EN")
  fi
  "$python_bin" scripts/browser_checks.py "${browser_args_en[@]}"
  browser_status=$?
fi
set -e

if [[ $browser_status -eq 2 && ${REQUIRE_BROWSER_CHECKS:-0} != 1 ]]; then
  echo "AVERTISSEMENT : contrôles responsive et PDF ignorés." >&2
  echo "Installez le navigateur isolé dans le venv avec : make install-browser" >&2
  exit 0
fi
exit "$browser_status"
