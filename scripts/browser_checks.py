#!/usr/bin/env python3
"""Contrôle le responsive et le PDF avec le Chromium géré par Playwright."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys
import tempfile

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader
    import yaml
except ImportError as exc:
    print(
        "Playwright/pypdf indisponible. Exécutez : make install-browser",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DATA = yaml.safe_load((ROOT / "cv.yml").read_text(encoding="utf-8"))
VIEWPORTS = {
    "ordinateur": {"width": 1366, "height": 900},
    "tablette": {"width": 768, "height": 1024},
    "smartphone": {"width": 390, "height": 844},
}
THEMES = (
    "blue", "green", "red", "purple", "amber", "grey",
    "dark_blue", "dark_green", "dark_red", "dark_purple", "dark_amber", "dark_grey",
)


def expected_age() -> int:
    today = date.today()
    birth_date = SOURCE_DATA["person"]["birth_date"]
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def check_responsive(browser, page_url: str) -> None:
    for name, viewport in VIEWPORTS.items():
        page = browser.new_page(viewport=viewport)
        page.goto(page_url, wait_until="load")
        page.wait_for_function("document.documentElement.dataset.viewportFits !== undefined")
        metrics = page.evaluate(
            """() => ({
                fits: document.documentElement.dataset.viewportFits,
                overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                age: Array.from(document.querySelectorAll('[data-age]')).map(node => node.textContent.trim()),
                portrait: document.querySelector('.portrait').currentSrc,
                contactButtonWidth: document.querySelector('.contact-opener').getBoundingClientRect().width,
                printButtonWidth: document.querySelector('.print-button').getBoundingClientRect().width
            })"""
        )
        page.close()
        if metrics["fits"] != "true":
            raise AssertionError(f"débordement horizontal en vue {name} : {metrics['overflow']} px")
        if SOURCE_DATA["person"].get("show_age", True):
            expected = f"{expected_age()} ans"
            if not metrics["age"] or any(value != expected for value in metrics["age"]):
                raise AssertionError(f"âge dynamique incorrect en vue {name} : {metrics['age']}")
        elif metrics["age"]:
            raise AssertionError(f"âge affiché malgré person.show_age=false en vue {name}")
        photo_suffix = Path(SOURCE_DATA["person"]["photo"]).suffix.lower()
        expected_suffix = ".svg" if photo_suffix == ".svg" else ".avif"
        if not metrics["portrait"].endswith(expected_suffix):
            raise AssertionError(f"format attendu du portrait non sélectionné en vue {name}")
        if abs(metrics["contactButtonWidth"] - metrics["printButtonWidth"]) > 0.5:
            raise AssertionError(f"largeurs des boutons incohérentes en vue {name}")


def check_themes(browser, page_url: str) -> None:
    page = browser.new_page(viewport={"width": 1366, "height": 900})
    page.goto(page_url, wait_until="load")
    for theme in THEMES:
        result = page.evaluate(
            """theme => {
                document.documentElement.dataset.theme = theme;
                const styles = getComputedStyle(document.documentElement);
                const rgb = value => {
                    const probe = document.createElement('span');
                    probe.style.color = value.trim();
                    document.body.append(probe);
                    const channels = getComputedStyle(probe).color.match(/[\\d.]+/g).slice(0, 3).map(Number);
                    probe.remove();
                    return channels;
                };
                const luminance = value => {
                    const channels = rgb(value).map(v => {
                        v /= 255;
                        return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4;
                    });
                    return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2];
                };
                const ratio = (foreground, background) => {
                    const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
                    return (values[0] + .05) / (values[1] + .05);
                };
                const pairs = [
                    ['texte', '--ink', '--paper'], ['texte secondaire', '--muted', '--paper'],
                    ['titres', '--heading', '--paper'], ['liens', '--link', '--paper'],
                    ['bouton', '--button-ink', '--cyan']
                ];
                return {
                    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                    failures: pairs
                        .map(([label, foreground, background]) => [label, ratio(styles.getPropertyValue(foreground), styles.getPropertyValue(background))])
                        .filter(([, value]) => value < 4.5)
                };
            }""",
            theme,
        )
        if result["overflow"] > 0:
            raise AssertionError(f"débordement horizontal avec le thème {theme}")
        if result["failures"]:
            details = ", ".join(f"{label}: {ratio:.2f}" for label, ratio in result["failures"])
            raise AssertionError(f"contraste insuffisant avec le thème {theme} ({details})")

    page.evaluate("localStorage.removeItem('cv-color'); localStorage.removeItem('cv-mode')")
    page.emulate_media(color_scheme="dark")
    page.reload(wait_until="load")
    if page.locator("html").get_attribute("data-theme") != "dark_blue":
        raise AssertionError("la préférence sombre du navigateur n'est pas appliquée")
    page.emulate_media(color_scheme="light")
    page.reload(wait_until="load")
    if page.locator("html").get_attribute("data-theme") != "blue":
        raise AssertionError("la préférence claire du navigateur n'est pas appliquée")
    page.click("[data-theme-toggle]")
    if page.locator("#theme-panel").is_hidden():
        raise AssertionError("le sélecteur de thème ne s'ouvre pas")
    page.select_option("[data-theme-select]", "green")
    if page.locator("html").get_attribute("data-theme") != "green":
        raise AssertionError("le sélecteur de couleur n'applique pas le choix")
    page.click("[data-theme-mode]")
    if page.locator("html").get_attribute("data-theme") != "dark_green":
        raise AssertionError("le switch sombre n'applique pas le mode")
    page.reload(wait_until="load")
    if page.locator("html").get_attribute("data-theme") != "dark_green":
        raise AssertionError("le thème choisi n'est pas mémorisé")
    page.evaluate("localStorage.removeItem('cv-color'); localStorage.removeItem('cv-mode')")
    page.close()

    mobile_context = browser.new_context(
        viewport={"width": 390, "height": 844},
        is_mobile=True,
        has_touch=True,
        color_scheme="light",
    )
    mobile_context.add_init_script(
        "Storage.prototype.setItem = function () { throw new DOMException('Storage blocked'); };"
    )
    mobile_page = mobile_context.new_page()
    mobile_page.goto(page_url, wait_until="load")
    mobile_page.tap("[data-theme-toggle]")
    mobile_page.tap("[data-theme-mode]")
    if mobile_page.locator("html").get_attribute("data-theme") != "dark_blue":
        raise AssertionError("le switch sombre ne répond pas au toucher sur mobile")
    if mobile_page.locator("[data-theme-mode]").get_attribute("aria-checked") != "true":
        raise AssertionError("l'état du switch sombre mobile n'est pas exposé")
    mobile_context.close()


def generate_pdf(browser, page_url: str, destination: Path) -> None:
    page = browser.new_page()
    page.goto(page_url, wait_until="load")
    page.emulate_media(media="print")
    print_colors = page.evaluate(
        """() => {
            const styles = getComputedStyle(document.documentElement);
            const displayedColors = [
                getComputedStyle(document.querySelector('.hero')).borderTopColor,
                getComputedStyle(document.querySelector('h1')).color,
                getComputedStyle(document.querySelector('h2')).color
            ];
            const isGrey = color => {
                const channels = color.match(/[\\d.]+/g).slice(0, 3).map(Number);
                return channels[0] === channels[1] && channels[1] === channels[2];
            };
            return {
                background: styles.backgroundColor,
                colorScheme: styles.colorScheme,
                colorsAreGrey: displayedColors.every(isGrey),
                portraitFilter: getComputedStyle(document.querySelector('.portrait')).filter
            };
        }"""
    )
    if (
        print_colors["background"] != "rgb(255, 255, 255)"
        or print_colors["colorScheme"] != "light"
        or not print_colors["colorsAreGrey"]
        or "grayscale(1)" not in print_colors["portraitFilter"]
        or "brightness(1.1)" not in print_colors["portraitFilter"]
    ):
        raise AssertionError(f"fond d'impression incorrect : {print_colors}")
    page.pdf(
        path=str(destination),
        format="A4",
        print_background=True,
        prefer_css_page_size=True,
        display_header_footer=False,
    )
    page.close()


def check_pdf(path: Path) -> int:
    reader = PdfReader(path)
    pages = len(reader.pages)
    expected_pages = SOURCE_DATA["meta"]["pdf_pages"]
    if pages != expected_pages:
        raise AssertionError(f"le PDF contient {pages} pages, exactement {expected_pages} attendues")
    first_page = reader.pages[0]
    width = float(first_page.mediabox.width)
    height = float(first_page.mediabox.height)
    if abs(width - 595) > 2 or abs(height - 842) > 2:
        raise AssertionError(f"format PDF inattendu : {width:.1f} × {height:.1f} points")

    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    person = SOURCE_DATA["person"]
    required = [
        f'{person["first_name"]} {person["last_name"]}',
        person["email"],
        SOURCE_DATA["experiences"][-1]["company"],
    ]
    if person.get("driving_licence"):
        required.append(person["driving_licence"])
    if person.get("show_age", True):
        required.append(f"{expected_age()} ans")
    for value in required:
        if value not in extracted:
            raise AssertionError(f"contenu absent du PDF : {value}")

    qr_expected = "assets/cv-qr.svg" in (ROOT / "index.html").read_text(encoding="utf-8")
    if qr_expected != ("AJOUTER LE CONTACT" in " ".join(extracted.split())):
        raise AssertionError("état du QR code incohérent entre le HTML et le PDF")

    link_targets = []
    for page in reader.pages:
        for annotation_ref in page.get("/Annots", []):
            annotation = annotation_ref.get_object()
            action = annotation.get("/A")
            if action and action.get("/URI"):
                link_targets.append(action["/URI"])
    if SOURCE_DATA["meta"]["canonical_url"] not in link_targets:
        raise AssertionError("le lien vers le CV en ligne n'est pas cliquable dans le PDF")
    for profile in person["profiles"]:
        label = profile.get("username") or profile["url"].removeprefix("https://").removeprefix("www.")
        if profile["network"].casefold() not in extracted.casefold() or label not in extracted:
            raise AssertionError(f'profil absent du PDF : {profile["network"]}')
        if profile["url"] not in link_targets:
            raise AssertionError(f'lien de profil non cliquable dans le PDF : {profile["network"]}')
    if person.get("availability") and person["profiles"]:
        extracted_folded = extracted.casefold()
        last_profile = max(extracted_folded.find(profile["network"].casefold()) for profile in person["profiles"])
        status_position = extracted_folded.find("statut", last_profile)
        if status_position < last_profile:
            raise AssertionError("le statut doit apparaître après les profils dans le PDF")
        if person.get("availability_period") and extracted_folded.find("disponibilité", status_position) < status_position:
            raise AssertionError("la disponibilité doit apparaître après le statut dans le PDF")

    ordered = ("COMPÉTENCES TECHNIQUES", "CERTIFICATIONS", "FORMATION", "LANGUES", "CENTRES D’INTÉRÊT")
    positions = [extracted.find(section) for section in ordered]
    if -1 in positions or positions != sorted(positions):
        raise AssertionError("ordre de lecture ATS incorrect dans le PDF")
    return pages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-output", type=Path, help="conserver le PDF à cet emplacement")
    args = parser.parse_args()
    temporary_dir = None
    if args.pdf_output:
        pdf_path = args.pdf_output.resolve()
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        temporary_dir = tempfile.TemporaryDirectory()
        pdf_path = Path(temporary_dir.name) / "cv.pdf"

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
            except PlaywrightError as exc:
                print(
                    "Impossible de démarrer le Chromium de Playwright. "
                    "Installez ou réparez le navigateur et ses bibliothèques Linux avec : "
                    "make install-browser",
                    file=sys.stderr,
                )
                print(f"Détail Playwright : {exc}", file=sys.stderr)
                raise SystemExit(2) from exc
            page_url = (ROOT / "index.html").as_uri()
            check_responsive(browser, page_url)
            check_themes(browser, page_url)
            generate_pdf(browser, page_url, pdf_path)
            browser.close()
        pages = check_pdf(pdf_path)
    finally:
        if temporary_dir:
            temporary_dir.cleanup()

    print("Responsive Playwright ordinateur/tablette/smartphone : OK")
    print("Contraste des 6 couleurs en modes clair et sombre : OK")
    print(f"PDF Playwright A4 et ordre de lecture ATS : {pages} pages")
    if args.pdf_output:
        print(f"PDF généré : {pdf_path}")


if __name__ == "__main__":
    main()
