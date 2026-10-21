"""Génération des PDF : cartes d'élève, bulletins, certificats, fiches d'appel.

Ce module ne dépend pas de la base de données : il reçoit des dictionnaires
préparés par les vues et retourne les octets du PDF."""
from datetime import timedelta
from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

PRIMAIRE = colors.HexColor('#0f2557')
ACCENT = colors.HexColor('#0ea5e9')
CLAIR = colors.HexColor('#e8f1fb')
GRIS = colors.HexColor('#64748b')
TRAIT = colors.HexColor('#cbd5e1')

MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
        'septembre', 'octobre', 'novembre', 'décembre']
JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
TRIMESTRES = {1: '1er trimestre', 2: '2e trimestre', 3: '3e trimestre'}
DECISIONS = {'passant': 'PASSANT(E)', 'redoublant': 'REDOUBLANT(E)'}


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------
def fmt(v):
    """12.5 -> '12,50' ; None -> ''"""
    return '' if v is None else f"{float(v):.2f}".replace('.', ',')


def date_fr(d, court=False):
    if not d:
        return ''
    if court:
        return d.strftime('%d/%m/%Y')
    return f"{d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"


def _ajuster(texte, police, taille, largeur):
    """Raccourcit le texte (avec ...) pour qu'il tienne dans la largeur."""
    texte = str(texte or '')
    if stringWidth(texte, police, taille) <= largeur:
        return texte
    while texte and stringWidth(texte + '...', police, taille) > largeur:
        texte = texte[:-1]
    return texte + '...'


def _qr(c, valeur, x, y, taille):
    widget = qr.QrCodeWidget(str(valeur))
    x0, y0, x1, y1 = widget.getBounds()
    d = Drawing(taille, taille, transform=[taille / (x1 - x0), 0, 0, taille / (y1 - y0), 0, 0])
    d.add(widget)
    renderPDF.draw(d, c, x, y)


def _photo(c, octets, x, y, w, h, rond=False):
    """Dessine la photo en remplissant tout le cadre (recadrage centré, haut de
    l'image conservé pour garder le visage). Retourne False si elle est illisible."""
    if not octets:
        return False
    try:
        image = ImageReader(BytesIO(octets))
        iw, ih = image.getSize()
    except Exception:   # noqa: BLE001 - une photo abîmée ne doit pas bloquer l'impression
        return False
    echelle = max(w / iw, h / ih)
    dw, dh = iw * echelle, ih * echelle
    c.saveState()
    chemin = c.beginPath()
    if rond:
        chemin.circle(x + w / 2, y + h / 2, w / 2)
    else:
        chemin.roundRect(x, y, w, h, 1.5 * mm)
    c.clipPath(chemin, stroke=0, fill=0)
    c.drawImage(image, x + (w - dw) / 2, y + h - dh, dw, dh)
    c.restoreState()
    return True


def _nouveau(pagesize=A4):
    buf = BytesIO()
    return buf, canvas.Canvas(buf, pagesize=pagesize)


def _page_vide(c, message, pagesize=A4):
    c.setFont('Helvetica', 12)
    c.setFillColor(GRIS)
    c.drawCentredString(pagesize[0] / 2, pagesize[1] / 2, message)


def _en_tete(c, etab, largeur, hauteur_page, hauteur=26 * mm, x0=0):
    """Bandeau bleu avec le nom de l'école (x0 = décalage à gauche, largeur = largeur du bandeau)."""
    c.setFillColor(PRIMAIRE)
    c.rect(x0, hauteur_page - hauteur, largeur, hauteur, stroke=0, fill=1)
    c.setFillColor(ACCENT)
    c.rect(x0, hauteur_page - hauteur - 1.2 * mm, largeur, 1.2 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 16)
    c.drawCentredString(x0 + largeur / 2, hauteur_page - 11 * mm,
                        _ajuster(etab['nom'], 'Helvetica-Bold', 16, largeur - 40 * mm))
    infos = ' · '.join(x for x in (etab.get('adresse'), etab.get('ville'), etab.get('telephone')) if x)
    c.setFont('Helvetica', 8)
    c.drawCentredString(x0 + largeur / 2, hauteur_page - 17 * mm, _ajuster(infos, 'Helvetica', 8, largeur - 40 * mm))
    if etab.get('email'):
        c.drawCentredString(x0 + largeur / 2, hauteur_page - 21.5 * mm, etab['email'])


# ---------------------------------------------------------------------------
# Cartes d'élève (8 par page A4)
# ---------------------------------------------------------------------------
def cartes_pdf(cartes, etab):
    buf, c = _nouveau()
    W, H = A4
    cw, ch, cols, rows = 85.6 * mm, 54 * mm, 2, 4
    gx, gy = 10 * mm, 8 * mm
    mx = (W - (cols * cw + (cols - 1) * gx)) / 2
    my = (H - (rows * ch + (rows - 1) * gy)) / 2

    if not cartes:
        _page_vide(c, 'Aucune carte à imprimer')
    for i, carte in enumerate(cartes):
        pos = i % (cols * rows)
        if pos == 0 and i > 0:
            c.showPage()
        x = mx + (pos % cols) * (cw + gx)
        y = H - my - (pos // cols + 1) * ch - (pos // cols) * gy
        _carte(c, x, y, cw, ch, carte, etab)
    c.save()
    return buf.getvalue()


def _carte(c, x, y, w, h, carte, etab):
    c.saveState()
    chemin = c.beginPath()
    chemin.roundRect(x, y, w, h, 3 * mm)
    c.clipPath(chemin, stroke=0, fill=0)
    c.setFillColor(colors.white)
    c.rect(x, y, w, h, stroke=0, fill=1)
    # bandeau supérieur
    c.setFillColor(PRIMAIRE)
    c.rect(x, y + h - 12 * mm, w, 12 * mm, stroke=0, fill=1)
    c.setFillColor(ACCENT)
    c.rect(x, y + h - 13 * mm, w, 1 * mm, stroke=0, fill=1)
    # bas
    c.setFillColor(CLAIR)
    c.rect(x, y, w, 7 * mm, stroke=0, fill=1)
    c.restoreState()

    c.setStrokeColor(TRAIT)
    c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, 3 * mm, stroke=1, fill=0)

    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 8.5)
    c.drawCentredString(x + w / 2, y + h - 5.5 * mm, _ajuster(etab['nom'], 'Helvetica-Bold', 8.5, w - 8 * mm))
    c.setFont('Helvetica', 6.5)
    c.drawCentredString(x + w / 2, y + h - 9.5 * mm, "CARTE D'ÉLÈVE")

    # photo de l'élève, ou ses initiales s'il n'a pas de photo
    cx, cy = x + 14 * mm, y + h - 27 * mm
    c.setFillColor(CLAIR)
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1)
    if _photo(c, carte.get('photo'), cx - 10 * mm, cy - 10 * mm, 20 * mm, 20 * mm, rond=True):
        c.circle(cx, cy, 10 * mm, stroke=1, fill=0)
    else:
        c.circle(cx, cy, 9 * mm, stroke=1, fill=1)
        c.setFillColor(PRIMAIRE)
        c.setFont('Helvetica-Bold', 15)
        initiales = ((carte['prenom'] or ' ')[0] + (carte['nom'] or ' ')[0]).upper()
        c.drawCentredString(cx, cy - 2 * mm, initiales)

    tx, largeur_txt = x + 27 * mm, w - 27 * mm - 21 * mm
    c.setFillColor(PRIMAIRE)
    c.setFont('Helvetica-Bold', 10)
    c.drawString(tx, y + h - 19 * mm, _ajuster((carte['nom'] or '').upper(), 'Helvetica-Bold', 10, largeur_txt))
    c.setFont('Helvetica', 9)
    c.drawString(tx, y + h - 23.5 * mm, _ajuster(carte['prenom'], 'Helvetica', 9, largeur_txt))
    c.setFillColor(colors.HexColor('#334155'))
    c.setFont('Helvetica', 7.5)
    lignes = [f"Classe : {carte['classe']}"]
    if carte.get('numero'):
        lignes.append(f"N° : {carte['numero']}")
    if carte.get('date_naissance'):
        lignes.append(f"Né(e) le : {date_fr(carte['date_naissance'], court=True)}")
    for k, texte in enumerate(lignes):
        c.drawString(tx, y + h - 28.5 * mm - k * 3.8 * mm, _ajuster(texte, 'Helvetica', 7.5, largeur_txt))

    _qr(c, carte['matricule'] or '', x + w - 19 * mm, y + 8.5 * mm, 16 * mm)

    c.setFillColor(PRIMAIRE)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawString(x + 4 * mm, y + 2.4 * mm, f"Matricule : {carte['matricule'] or '—'}")
    c.setFont('Helvetica', 7)
    c.drawRightString(x + w - 4 * mm, y + 2.4 * mm, f"Année {carte['annee']}")


# ---------------------------------------------------------------------------
# Bulletins scolaires
# ---------------------------------------------------------------------------
def bulletins_pdf(bulletins, etab):
    buf, c = _nouveau()
    if not bulletins:
        _page_vide(c, 'Aucun bulletin à imprimer')
    for i, b in enumerate(bulletins):
        if i:
            c.showPage()
        _bulletin(c, b, etab)
    c.save()
    return buf.getvalue()


def _bulletin(c, b, etab):
    W, H = A4
    m = 15 * mm
    _en_tete(c, etab, W, H)

    c.setFillColor(PRIMAIRE)
    c.setFont('Helvetica-Bold', 15)
    c.drawCentredString(W / 2, H - 38 * mm, 'BULLETIN SCOLAIRE')
    c.setFont('Helvetica', 10)
    c.setFillColor(GRIS)
    c.drawCentredString(W / 2, H - 44 * mm, f"{TRIMESTRES[b['trimestre']]} · Année scolaire {b['annee']}")

    # Identité
    top = H - 50 * mm
    c.setFillColor(CLAIR)
    c.setStrokeColor(TRAIT)
    c.roundRect(m, top - 22 * mm, W - 2 * m, 22 * mm, 2 * mm, stroke=1, fill=1)
    c.setFillColor(colors.HexColor('#0f172a'))

    avec_photo = bool(b.get('photo'))
    if avec_photo:
        _photo(c, b['photo'], W - m - 19 * mm, top - 20 * mm, 16 * mm, 18 * mm)

    def champ(x, y, libelle, valeur, largeur=78 * mm):
        c.setFont('Helvetica', 8)
        c.setFillColor(GRIS)
        c.drawString(x, y, libelle)
        c.setFont('Helvetica-Bold', 10)
        c.setFillColor(colors.HexColor('#0f172a'))
        c.drawString(x, y - 4.2 * mm, _ajuster(valeur, 'Helvetica-Bold', 10, largeur))

    largeur2 = 62 * mm if avec_photo else 78 * mm
    champ(m + 4 * mm, top - 5 * mm, 'Nom et prénom', f"{(b['nom'] or '').upper()} {b['prenom']}")
    champ(m + 4 * mm, top - 14.5 * mm, 'Né(e) le', date_fr(b['date_naissance'], court=True) or '—')
    champ(W / 2 + 2 * mm, top - 5 * mm, 'Classe', f"{b['classe']}   (N° {b['numero'] or '—'} / effectif {b['effectif']})", largeur2)
    champ(W / 2 + 2 * mm, top - 14.5 * mm, 'Matricule', b['matricule'] or '—', largeur2)

    # Tableau des notes
    entetes = ['Matière', 'Coef', 'J1', 'J2', 'J3', 'Moy. J', 'Exam.', 'Moyenne', 'Moy × Coef']
    donnees = [entetes]
    for l in b['lignes']:
        donnees.append([
            _ajuster(l['matiere'], 'Helvetica', 9, 54 * mm), l['coef'],
            fmt(l['j1']), fmt(l['j2']), fmt(l['j3']), fmt(l['moy_j']),
            fmt(l['examen']), fmt(l['moyenne']), fmt(l['points']),
        ])
    donnees.append(['TOTAL', b['total_coef'], '', '', '', '', '', '', fmt(b['total_points'])])
    largeurs = [54 * mm, 13 * mm, 14 * mm, 14 * mm, 14 * mm, 16 * mm, 14 * mm, 18 * mm, 23 * mm]
    t = Table(donnees, colWidths=largeurs, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMAIRE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f1f5f9')]),
        ('FONTNAME', (7, 1), (7, -2), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), CLAIR),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.4, TRAIT),
        ('TOPPADDING', (0, 0), (-1, -1), 3.2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.2),
    ]))
    _, th = t.wrapOn(c, W - 2 * m, H)
    ty = top - 28 * mm - th
    t.drawOn(c, m, ty)

    # Bilan
    by = ty - 8 * mm
    bh = 30 * mm
    c.setFillColor(colors.white)
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.2)
    c.roundRect(m, by - bh, W - 2 * m, bh, 2 * mm, stroke=1, fill=0)

    c.setFillColor(GRIS)
    c.setFont('Helvetica', 8)
    c.drawString(m + 5 * mm, by - 6 * mm, 'MOYENNE GÉNÉRALE')
    c.setFillColor(PRIMAIRE)
    c.setFont('Helvetica-Bold', 24)
    c.drawString(m + 5 * mm, by - 17 * mm, fmt(b['generale']) or '—')
    c.setFont('Helvetica', 9)
    c.drawString(m + 5 * mm, by - 24 * mm, '/ 20')

    rang = f"{b['rang']}{'er' if b['rang'] == 1 else 'e'} / {b['effectif']}" if b['rang'] else '—'
    x2 = m + 52 * mm
    c.setFillColor(GRIS)
    c.setFont('Helvetica', 8)
    c.drawString(x2, by - 6 * mm, 'RANG')
    c.setFillColor(PRIMAIRE)
    c.setFont('Helvetica-Bold', 14)
    c.drawString(x2, by - 14 * mm, rang)
    c.setFillColor(GRIS)
    c.setFont('Helvetica', 8)
    c.drawString(x2, by - 20 * mm, f"Moyenne de la classe : {fmt(b['stats']['moyenne']) or '—'}")
    c.drawString(x2, by - 24.5 * mm, f"Plus forte : {fmt(b['stats']['max']) or '—'}   Plus faible : {fmt(b['stats']['min']) or '—'}")

    x3 = m + 112 * mm
    c.setFont('Helvetica', 8)
    c.drawString(x3, by - 6 * mm, 'APPRÉCIATION')
    c.setFillColor(PRIMAIRE)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(x3, by - 13 * mm, b['appreciation'] or '—')

    # Synthèse annuelle
    ay = by - bh - 8 * mm
    resume = [['', '1er trim.', '2e trim.', '3e trim.', 'Année'],
              ['Moyenne', *(fmt(b['generales'].get(t)) or '—' for t in (1, 2, 3)), fmt(b['annuelle']) or '—']]
    t2 = Table(resume, colWidths=[28 * mm, 24 * mm, 24 * mm, 24 * mm, 24 * mm])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), CLAIR), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, 1), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'), ('GRID', (0, 0), (-1, -1), 0.4, TRAIT),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    _, h2 = t2.wrapOn(c, 130 * mm, 40 * mm)
    t2.drawOn(c, m, ay - h2)
    if b.get('decision') in DECISIONS:
        c.setFillColor(ACCENT if b['decision'] == 'passant' else colors.HexColor('#e11d48'))
        c.roundRect(m + 128 * mm, ay - h2, 52 * mm, h2, 2 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 9.5)
        c.drawCentredString(m + 154 * mm, ay - h2 + h2 / 2 - 1.5 * mm, f"DÉCISION : {DECISIONS[b['decision']]}")

    # Signatures
    sy = 28 * mm
    c.setFillColor(colors.HexColor('#0f172a'))
    c.setFont('Helvetica', 9)
    c.drawString(m, sy, 'Signature des parents')
    c.drawRightString(W - m, sy, 'Le Directeur')
    if etab.get('directeur'):
        c.setFont('Helvetica-Bold', 9)
        c.drawRightString(W - m, sy - 14 * mm, etab['directeur'])
    c.setStrokeColor(TRAIT)
    c.line(m, sy - 2 * mm, m + 50 * mm, sy - 2 * mm)
    c.line(W - m - 50 * mm, sy - 2 * mm, W - m, sy - 2 * mm)


# ---------------------------------------------------------------------------
# Certificats de scolarité
# ---------------------------------------------------------------------------
def certificats_pdf(certificats, etab, aujourdhui):
    buf, c = _nouveau()
    if not certificats:
        _page_vide(c, 'Aucun certificat à imprimer')
    for i, cert in enumerate(certificats):
        if i:
            c.showPage()
        _certificat(c, cert, etab, aujourdhui)
    c.save()
    return buf.getvalue()


def _certificat(c, cert, etab, aujourdhui):
    W, H = A4
    m = 18 * mm
    c.setStrokeColor(PRIMAIRE)
    c.setLineWidth(2)
    c.rect(8 * mm, 8 * mm, W - 16 * mm, H - 16 * mm, stroke=1, fill=0)
    c.setStrokeColor(ACCENT)
    c.setLineWidth(0.6)
    c.rect(10.5 * mm, 10.5 * mm, W - 21 * mm, H - 21 * mm, stroke=1, fill=0)
    _en_tete(c, etab, W - 21 * mm, H - 10.5 * mm, hauteur=26 * mm, x0=10.5 * mm)  # bandeau intérieur

    c.setFillColor(PRIMAIRE)
    c.setFont('Helvetica-Bold', 22)
    c.drawCentredString(W / 2, H - 62 * mm, 'CERTIFICAT DE SCOLARITÉ')
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.5)
    c.line(W / 2 - 40 * mm, H - 66 * mm, W / 2 + 40 * mm, H - 66 * mm)

    f = cert['sexe'] == 'F'
    style = ParagraphStyle('corps', fontName='Helvetica', fontSize=12, leading=21, alignment=TA_LEFT)
    directeur = etab.get('directeur') or 'le Directeur'
    intro = (f"Je soussigné(e), <b>{directeur}</b>, Directeur(trice) de <b>{etab['nom']}</b>, "
             "certifie que l’élève :")
    p = Paragraph(intro, style)
    _, h = p.wrapOn(c, W - 2 * m, 60 * mm)
    y = H - 84 * mm
    p.drawOn(c, m, y - h)
    y -= h + 8 * mm

    c.setFillColor(CLAIR)
    c.setStrokeColor(TRAIT)
    c.roundRect(m, y - 33 * mm, W - 2 * m, 33 * mm, 2 * mm, stroke=1, fill=1)
    lignes = [
        ('Nom et prénom', f"{(cert['nom'] or '').upper()} {cert['prenom']}"),
        (f"{'Née' if f else 'Né'} le", date_fr(cert['date_naissance']) or '—'),
        ('Matricule', cert['matricule'] or '—'),
    ]
    for k, (lib, val) in enumerate(lignes):
        c.setFillColor(GRIS)
        c.setFont('Helvetica', 10)
        c.drawString(m + 6 * mm, y - 9 * mm - k * 9 * mm, lib)
        c.setFillColor(colors.HexColor('#0f172a'))
        c.setFont('Helvetica-Bold', 12)
        c.drawString(m + 48 * mm, y - 9 * mm - k * 9 * mm, val)
    y -= 33 * mm + 9 * mm

    corps = (f"est régulièrement {'inscrite' if f else 'inscrit'} en classe de <b>{cert['classe']}</b> "
             f"au titre de l’année scolaire <b>{cert['annee']}</b> dans notre établissement.<br/><br/>"
             f"Ce certificat est délivré à l’intéressé(e) pour servir et valoir ce que de droit.")
    p2 = Paragraph(corps, style)
    _, h2 = p2.wrapOn(c, W - 2 * m, 80 * mm)
    p2.drawOn(c, m, y - h2)
    y -= h2 + 16 * mm

    c.setFillColor(colors.HexColor('#0f172a'))
    c.setFont('Helvetica', 11)
    lieu = f"Fait à {etab['ville']}, le " if etab.get('ville') else 'Fait le '
    c.drawRightString(W - m, y, lieu + date_fr(aujourdhui))
    c.setFont('Helvetica-Bold', 11)
    c.drawRightString(W - m, y - 9 * mm, 'Le Directeur')
    if etab.get('directeur'):
        c.setFont('Helvetica', 11)
        c.drawRightString(W - m, y - 32 * mm, etab['directeur'])


# ---------------------------------------------------------------------------
# Fiches d'appel (présence de la semaine)
# ---------------------------------------------------------------------------
def fiches_appel_pdf(fiches, debut_semaine, etab):
    taille = landscape(A4)
    buf, c = _nouveau(taille)
    W, H = taille
    premiere = True
    if not fiches:
        _page_vide(c, "Aucune fiche à imprimer", taille)
    for fiche in fiches:
        eleves = fiche['eleves']
        par_page = 21
        morceaux = [eleves[i:i + par_page] for i in range(0, len(eleves), par_page)] or [[]]
        for k, morceau in enumerate(morceaux):
            if not premiere:
                c.showPage()
            premiere = False
            _page_appel(c, fiche, morceau, k + 1, len(morceaux), debut_semaine, etab, W, H)
    c.save()
    return buf.getvalue()


def _page_appel(c, fiche, eleves, page, nb_pages, debut, etab, W, H):
    m = 10 * mm
    c.setFillColor(PRIMAIRE)
    c.rect(0, H - 17 * mm, W, 17 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 13)
    c.drawString(m, H - 8 * mm, _ajuster(etab['nom'], 'Helvetica-Bold', 13, 140 * mm))
    c.setFont('Helvetica', 8.5)
    c.drawString(m, H - 13.5 * mm, 'FICHE D’APPEL / DE PRÉSENCE')
    c.setFont('Helvetica-Bold', 14)
    c.drawRightString(W - m, H - 8 * mm, f"Classe : {fiche['classe']}")
    c.setFont('Helvetica', 9)
    semaine = ''
    if debut:
        semaine = f"Semaine du {date_fr(debut, True)} au {date_fr(debut + timedelta(days=5), True)}"
    c.drawRightString(W - m, H - 13.5 * mm,
                      f"Année {fiche['annee']}" + (f"  ·  {semaine}" if semaine else '')
                      + (f"  ·  page {page}/{nb_pages}" if nb_pages > 1 else ''))

    # Tableau
    ligne_jours = ['N°', 'Nom et prénom']
    ligne_sous = ['', '']
    for i, j in enumerate(JOURS):
        etiquette = j
        if debut:
            etiquette += f"\n{(debut + timedelta(days=i)).strftime('%d/%m')}"
        ligne_jours += [etiquette, '']
        ligne_sous += ['Matin', 'Après-m.']
    ligne_jours.append('Observations')
    ligne_sous.append('')
    donnees = [ligne_jours, ligne_sous]
    for e in eleves:
        donnees.append([e['numero'] or '', _ajuster(f"{(e['nom'] or '').upper()} {e['prenom']}", 'Helvetica', 8.5, 62 * mm)]
                       + [''] * 12 + [''])
    largeurs = [9 * mm, 64 * mm] + [12.2 * mm] * 12 + [W - 2 * m - 9 * mm - 64 * mm - 12.2 * mm * 12]
    t = Table(donnees, colWidths=largeurs, rowHeights=[9 * mm, 5 * mm] + [7.2 * mm] * len(eleves))
    style = [
        ('BACKGROUND', (0, 0), (-1, 1), PRIMAIRE), ('TEXTCOLOR', (0, 0), (-1, 1), colors.white),
        ('FONTNAME', (0, 0), (-1, 1), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, 0), 8.5),
        ('FONTSIZE', (2, 1), (-2, 1), 5.5), ('FONTSIZE', (0, 2), (-1, -1), 8.5),
        ('ALIGN', (0, 0), (-1, 1), 'CENTER'), ('ALIGN', (0, 2), (0, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, TRAIT),
        ('SPAN', (0, 0), (0, 1)), ('SPAN', (1, 0), (1, 1)), ('SPAN', (-1, 0), (-1, 1)),
        ('ROWBACKGROUNDS', (0, 2), (-1, -1), [colors.white, colors.HexColor('#f1f5f9')]),
    ]
    for i in range(6):
        style += [('SPAN', (2 + 2 * i, 0), (3 + 2 * i, 0)),
                  ('LINEAFTER', (3 + 2 * i, 0), (3 + 2 * i, -1), 1.1, PRIMAIRE)]
    t.setStyle(TableStyle(style))
    _, th = t.wrapOn(c, W - 2 * m, H)
    t.drawOn(c, m, H - 22 * mm - th)

    c.setFillColor(GRIS)
    c.setFont('Helvetica', 8)
    c.drawString(m, 8 * mm, 'P = présent · A = absent · R = retard   |   Matière / Professeur : ______________________________')
    c.drawRightString(W - m, 8 * mm, 'Visa du surveillant : ____________________')
